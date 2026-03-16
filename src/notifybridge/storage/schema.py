from __future__ import annotations

import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    api_key TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    api_key TEXT,
    source_ip TEXT,
    source_type TEXT NOT NULL,
    assignment_type TEXT NOT NULL,
    state TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    source_type TEXT NOT NULL,
    auth_status TEXT NOT NULL,
    api_key_candidate TEXT,
    summary TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);
"""


def init_db(connection: sqlite3.Connection) -> None:
    """Create all required tables if they do not already exist.

    Inputs:
    - `connection`: open SQLite connection.

    Outputs:
    - Applies schema DDL and commits it on the provided connection.
    """
    connection.executescript(SCHEMA)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(api_keys)").fetchall()}
    if "enabled" not in columns:
        connection.execute("ALTER TABLE api_keys ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
    notification_columns = {row[1] for row in connection.execute("PRAGMA table_info(notifications)").fetchall()}
    if "source_ip" not in notification_columns:
        connection.execute("ALTER TABLE notifications ADD COLUMN source_ip TEXT")
    connection.commit()
