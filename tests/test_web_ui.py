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
    assert "New key" in response.text
    assert "random-button" in response.text
    assert "clear-all-button" in response.text
    assert 'id="overview"' in response.text
    assert 'id="keys-panel"' in response.text
    assert 'id="audit-panel"' in response.text
    assert 'data-collapsed="true"' in response.text
    assert "Expand Audit Log" in response.text
    assert "All keys" in response.text
    assert "notification-state-button" in response.text
    assert "View: Unread" in response.text
    assert 'id="usage-tip"' in response.text
    assert 'id="syslog-mode-button"' in response.text
    assert 'data-email-domain="notifybridge.local"' in response.text
    assert "panel-subtitle" in response.text
    css = client.get("/static/app.css")
    js = client.get("/static/app.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert "overview-card" in css.text
    assert "empty-state" in css.text
    assert "pill" in css.text
    assert "key-card" in css.text
    assert "count-summary" in css.text
    assert "status-dot" in css.text
    assert "icon-trash" in css.text
    assert "icon-power" in css.text
    assert "icon-info" in css.text
    assert "active-filter" in css.text
    assert "dimmed-filter" in css.text
    assert "audit-failed" in css.text
    assert "notification-actions" in css.text
    assert "usage-tip-card" in css.text
    assert "usage-tip-overlay" in css.text
    assert "auditClasses" in js.text
    assert "renderOverview" in js.text
    assert "renderEmptyState" in js.text
    assert "notificationStateFilter = \"new\"" in js.text
    assert "mark-read" in js.text
    assert "source_ip" in js.text
    assert "usage-tip-key" in js.text
    assert "Show send guide" in js.text
    assert "buildUsageTip" in js.text
    assert "Delete key" in js.text
    assert "Enable key" in js.text
    assert "event.key === \"Escape\"" in js.text
    assert "/api/settings/syslog-mode" in js.text
    assert "Syslog: Strict" in js.text
    assert "logger -n" in js.text
    assert "mail -s 'NotifyBridge demo'" in js.text
    assert "/ingest/webhook/" in js.text
