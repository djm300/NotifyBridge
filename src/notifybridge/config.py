from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(slots=True)
class Settings:
    """Runtime configuration contract.

    Inputs:
    - Values are provided by `load_settings`, typically from environment variables.

    Outputs:
    - A strongly typed settings object used by runtime bootstrap, listeners, and UI code.

    Why the decorator is used:
    - `@dataclass` generates the value-object boilerplate needed for configuration
      storage while keeping the settings contract explicit and type-checked.
    """
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
        """Return whether syslog should accept unkeyed messages.

        Inputs:
        - Uses `self.syslog_mode`.

        Outputs:
        - `True` when syslog runs in permissive mode, otherwise `False`.
        """
        return self.syslog_mode.lower() == "permissive"


def load_settings() -> Settings:
    """Load application settings from environment variables.

    Inputs:
    - Reads `NOTIFYBRIDGE_*` environment variables when present.

    Outputs:
    - A populated `Settings` instance with defaults applied for missing values.
    """
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
