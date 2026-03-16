from fastapi.testclient import TestClient

from notifybridge.api.app import create_app
from notifybridge.config import load_settings
from notifybridge.runtime import build_runtime


def test_root_html_and_static_assets(tmp_path):
    settings = load_settings()
    settings.sqlite_path = tmp_path / "db.sqlite"
    client = TestClient(create_app(build_runtime(settings)))
    response = client.get("/")
    assert response.status_code == 200
    assert "theme-toggle" in response.text
    assert "Generate key" in response.text
    assert "random-button" in response.text
    assert "clear-all-button" in response.text
    assert 'id="audit-panel"' in response.text
    assert 'data-collapsed="true"' in response.text
    assert "Expand Audit Log" in response.text
    assert "Filter" in response.text
    css = client.get("/static/app.css")
    js = client.get("/static/app.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert "active-filter" in css.text
    assert "dimmed-filter" in css.text
