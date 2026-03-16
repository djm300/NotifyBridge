from pathlib import Path

from notifybridge.config import load_settings
from notifybridge.runtime import build_runtime


def test_load_settings_defaults(monkeypatch):
    monkeypatch.delenv("NOTIFYBRIDGE_SQLITE_PATH", raising=False)
    settings = load_settings()
    assert settings.sqlite_path == Path("notifybridge.db")
    assert settings.http_port == 8000
    assert settings.smtp_port == 2525
    assert settings.syslog_port == 5514
    assert settings.email_domain == "notifybridge.local"
    assert settings.syslog_mode == "strict"


def test_load_settings_env_overrides(monkeypatch, tmp_path):
    db = tmp_path / "app.db"
    monkeypatch.setenv("NOTIFYBRIDGE_SQLITE_PATH", str(db))
    monkeypatch.setenv("NOTIFYBRIDGE_SYSLOG_MODE", "permissive")
    monkeypatch.setenv("NOTIFYBRIDGE_EMAIL_DOMAIN", "example.local")
    settings = load_settings()
    assert settings.sqlite_path == db
    assert settings.permissive_syslog is True
    assert settings.email_domain == "example.local"


def test_build_runtime_with_empty_database(tmp_path):
    settings = load_settings()
    settings.sqlite_path = tmp_path / "notifybridge.db"
    runtime = build_runtime(settings)
    assert runtime.repository.list_api_keys() == []
    assert runtime.repository.list_notifications() == []
    assert runtime.repository.list_audit_entries() == []
