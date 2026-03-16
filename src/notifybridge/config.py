from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(slots=True)
class Settings:
    sqlite_path: Path = Path("notifybridge.db")
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 2525
    syslog_host: str = "127.0.0.1"
    syslog_port: int = 5514
    syslog_mode: str = "strict"
    email_domain: str = "notifybridge.local"
    theme_default: str = "dark"

    @property
    def permissive_syslog(self) -> bool:
        return self.syslog_mode.lower() == "permissive"


def load_settings() -> Settings:
    return Settings(
        sqlite_path=Path(os.getenv("NOTIFYBRIDGE_SQLITE_PATH", "notifybridge.db")),
        http_host=os.getenv("NOTIFYBRIDGE_HTTP_HOST", "127.0.0.1"),
        http_port=int(os.getenv("NOTIFYBRIDGE_HTTP_PORT", "8000")),
        smtp_host=os.getenv("NOTIFYBRIDGE_SMTP_HOST", "127.0.0.1"),
        smtp_port=int(os.getenv("NOTIFYBRIDGE_SMTP_PORT", "2525")),
        syslog_host=os.getenv("NOTIFYBRIDGE_SYSLOG_HOST", "127.0.0.1"),
        syslog_port=int(os.getenv("NOTIFYBRIDGE_SYSLOG_PORT", "5514")),
        syslog_mode=os.getenv("NOTIFYBRIDGE_SYSLOG_MODE", "strict"),
        email_domain=os.getenv("NOTIFYBRIDGE_EMAIL_DOMAIN", "notifybridge.local"),
        theme_default=os.getenv("NOTIFYBRIDGE_THEME_DEFAULT", "dark"),
    )
