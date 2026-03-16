from fastapi.testclient import TestClient
from starlette.requests import Request

from notifybridge.api.app import create_app
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
    response = client.post("/api/keys", json={"api_key": "team-red"})
    assert response.status_code == 201
    assert client.get("/api/keys").json()["keys"][0]["api_key"] == "team-red"

    ingest = client.post("/ingest/webhook/team-red", json={"title": "Build", "body": "ok"})
    assert ingest.status_code == 201
    items = client.get("/api/notifications", params={"api_key": "team-red"}).json()["items"]
    assert len(items) == 1
    notification_id = items[0]["id"]

    read = client.post(f"/api/notifications/{notification_id}/read")
    assert read.status_code == 200
    detail = client.get(f"/api/notifications/{notification_id}").json()
    assert detail["state"] == "read"

    deleted = client.delete(f"/api/notifications/{notification_id}")
    assert deleted.status_code == 200
    assert client.get("/api/notifications").json()["items"] == []
    runtime.repository.remove_api_key("team-red")


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


async def test_event_stream_and_validation(tmp_path):
    client, _runtime = make_client(tmp_path)
    invalid = client.post("/api/notifications/bulk-delete", json={"ids": "bad"})
    assert invalid.status_code == 400
    missing = client.get("/api/notifications/999")
    assert missing.status_code == 404
    scope = {"type": "http", "app": client.app, "method": "GET", "path": "/api/events", "headers": []}
    request = Request(scope)
    response = await event_stream(request)
    assert response.media_type == "text/event-stream"
