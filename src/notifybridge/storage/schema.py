from __future__ import annotations

import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    api_key TEXT PRIMARY KEY,
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
    connection.executescript(SCHEMA)
    connection.commit()
