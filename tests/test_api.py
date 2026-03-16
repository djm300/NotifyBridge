from fastapi.testclient import TestClient
from starlette.requests import Request

from notifybridge.api.app import create_app
from notifybridge.api import routes
from notifybridge.api.routes import event_stream
from notifybridge.config import load_settings
from notifybridge.runtime import build_runtime


def make_client(tmp_path):
    settings = load_settings()
    settings.sqlite_path = tmp_path / "db.sqlite"
    runtime = build_runtime(settings)
    return TestClient(create_app(runtime)), runtime


def test_key_crud_and_notifications_flow(tmp_path):
    client, runtime = make_client(tmp_path)
    response = client.post("/api/keys", json={})
    assert response.status_code == 201
    api_key = response.json()["api_key"]
    assert len(api_key) == 20
    assert client.get("/api/keys").json()["keys"][0]["api_key"] == api_key
    toggle = client.post(f"/api/keys/{api_key}/enabled", json={"enabled": False})
    assert toggle.status_code == 200
    assert client.get("/api/keys").json()["keys"][0]["enabled"] is False

    rejected = client.post(f"/ingest/webhook/{api_key}", json={"title": "Build", "body": "ok"})
    assert rejected.status_code == 202

    client.post(f"/api/keys/{api_key}/enabled", json={"enabled": True})

    ingest = client.post(f"/ingest/webhook/{api_key}", json={"title": "Build", "body": "ok"})
    assert ingest.status_code == 201
    items = client.get("/api/notifications", params={"api_key": api_key}).json()["items"]
    assert len(items) == 1
    assert items[0]["source_ip"] == "testclient"
    notification_id = items[0]["id"]

    read = client.post(f"/api/notifications/{notification_id}/read")
    assert read.status_code == 200
    detail = client.get(f"/api/notifications/{notification_id}").json()
    assert detail["state"] == "read"

    deleted = client.delete(f"/api/notifications/{notification_id}")
    assert deleted.status_code == 200
    assert client.get("/api/notifications").json()["items"] == []
    syslog_mode = client.post("/api/settings/syslog-mode", json={"allow_without_api": True})
    assert syslog_mode.status_code == 200
    assert syslog_mode.json()["allow_without_api"] is True
    assert client.get("/api/keys").json()["unassigned"]["enabled"] is True
    runtime.repository.remove_api_key(api_key)


def test_bulk_delete_clear_and_audit(tmp_path):
    client, runtime = make_client(tmp_path)
    runtime.repository.add_api_key("team-red")
    client.post("/ingest/webhook/team-red", json={"title": "One"})
    client.post("/ingest/webhook/team-red", json={"title": "Two"})
    client.post("/ingest/webhook/missing", json={"title": "Three"})
    items = client.get("/api/notifications", params={"api_key": "team-red"}).json()["items"]
    response = client.post("/api/notifications/bulk-delete", json={"ids": [items[0]["id"]]})
    assert response.status_code == 200
    clear = client.delete("/api/notifications/by-key/team-red")
    assert clear.status_code == 200
    assert client.get("/api/notifications").json()["items"] == []
    audit = client.get("/api/audit").json()["items"]
    assert audit[0]["source_type"] == "webhook"


def test_clear_all_and_random_demo_routes(tmp_path, monkeypatch):
    client, runtime = make_client(tmp_path)
    runtime.repository.add_api_key("team-red")
    client.post("/ingest/webhook/team-red", json={"title": "One"})
    client.post("/ingest/webhook/missing", json={"title": "Rejected"})
    assert len(client.get("/api/audit").json()["items"]) == 2
    cleared = client.delete("/api/notifications")
    assert cleared.status_code == 200
    assert client.get("/api/notifications").json()["items"] == []
    assert client.get("/api/audit").json()["items"] == []

    async def fake_seed_random_demo(settings, count=5):
        runtime.repository.add_api_key("AbCdEf0123456789ZyXw")
        runtime.repository.create_notification(
            api_key="AbCdEf0123456789ZyXw",
            source_ip="127.0.0.1",
            source_type="webhook",
            assignment_type="api_key",
            title="demo",
            body="demo",
            raw_payload="{}",
            metadata={},
        )
        return ["AbCdEf0123456789ZyXw"]

    monkeypatch.setattr(routes, "seed_random_demo", fake_seed_random_demo)
    seeded = client.post("/api/demo/random")
    assert seeded.status_code == 200
    assert seeded.json()["keys"] == ["AbCdEf0123456789ZyXw"]
    assert client.get("/api/notifications").json()["items"][0]["title"] == "demo"


def test_delete_key_removes_key_notifications(tmp_path):
    client, runtime = make_client(tmp_path)
    runtime.repository.add_api_key("team-red")
    client.post("/ingest/webhook/team-red", json={"title": "One"})
    assert len(client.get("/api/notifications").json()["items"]) == 1
    deleted = client.delete("/api/keys/team-red")
    assert deleted.status_code == 200
    assert client.get("/api/notifications").json()["items"] == []


async def test_event_stream_and_validation(tmp_path):
    client, _runtime = make_client(tmp_path)
    invalid = client.post("/api/notifications/bulk-delete", json={"ids": "bad"})
    assert invalid.status_code == 400
    invalid_syslog_mode = client.post("/api/settings/syslog-mode", json={"allow_without_api": "bad"})
    assert invalid_syslog_mode.status_code == 400
    missing = client.get("/api/notifications/999")
    assert missing.status_code == 404
    scope = {"type": "http", "app": client.app, "method": "GET", "path": "/api/events", "headers": []}
    request = Request(scope)
    response = await event_stream(request)
    assert response.media_type == "text/event-stream"
