from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from notifybridge.core.models import AuditEntry, KeySummary, Notification
from notifybridge.storage.schema import init_db


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Repository:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        self._ensure_db()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_db(self) -> None:
        with self.connection() as conn:
            init_db(conn)

    def add_api_key(self, api_key: str) -> None:
        with self.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO api_keys(api_key) VALUES (?)", (api_key,))

    def remove_api_key(self, api_key: str) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM api_keys WHERE api_key = ?", (api_key,))

    def list_api_keys(self) -> list[str]:
        with self.connection() as conn:
            rows = conn.execute("SELECT api_key FROM api_keys ORDER BY api_key").fetchall()
        return [row["api_key"] for row in rows]

    def has_api_key(self, api_key: str | None) -> bool:
        if not api_key:
            return False
        with self.connection() as conn:
            row = conn.execute("SELECT 1 FROM api_keys WHERE api_key = ?", (api_key,)).fetchone()
        return row is not None

    def set_syslog_mode(self, permissive: bool) -> None:
        value = "permissive" if permissive else "strict"
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES('syslog_mode', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (value,),
            )

    def get_syslog_mode(self) -> str:
        with self.connection() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'syslog_mode'").fetchone()
        return row["value"] if row else "strict"

    def create_notification(
        self,
        *,
        api_key: str | None,
        source_type: str,
        assignment_type: str,
        title: str,
        body: str,
        raw_payload: str,
        metadata: dict[str, Any],
        state: str = "new",
    ) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO notifications(
                    received_at, api_key, source_type, assignment_type, state,
                    title, body, raw_payload, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    api_key,
                    source_type,
                    assignment_type,
                    state,
                    title,
                    body,
                    raw_payload,
                    json.dumps(metadata, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def create_audit_entry(
        self,
        *,
        source_type: str,
        auth_status: str,
        api_key_candidate: str | None,
        summary: str,
        raw_payload: str,
        metadata: dict[str, Any],
    ) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_log(
                    received_at, source_type, auth_status, api_key_candidate,
                    summary, raw_payload, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    source_type,
                    auth_status,
                    api_key_candidate,
                    summary,
                    raw_payload,
                    json.dumps(metadata, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def _row_to_notification(self, row: sqlite3.Row) -> Notification:
        return Notification(
            id=row["id"],
            received_at=row["received_at"],
            api_key=row["api_key"],
            source_type=row["source_type"],
            assignment_type=row["assignment_type"],
            state=row["state"],
            title=row["title"],
            body=row["body"],
            raw_payload=row["raw_payload"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _row_to_audit(self, row: sqlite3.Row) -> AuditEntry:
        return AuditEntry(
            id=row["id"],
            received_at=row["received_at"],
            source_type=row["source_type"],
            auth_status=row["auth_status"],
            api_key_candidate=row["api_key_candidate"],
            summary=row["summary"],
            raw_payload=row["raw_payload"],
            metadata=json.loads(row["metadata_json"]),
        )

    def list_notifications(self, api_key: str | None = None, assignment_type: str | None = None) -> list[Notification]:
        query = "SELECT * FROM notifications"
        params: list[Any] = []
        clauses: list[str] = []
        if api_key is not None:
            clauses.append("api_key = ?")
            params.append(api_key)
        if assignment_type is not None:
            clauses.append("assignment_type = ?")
            params.append(assignment_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC"
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def get_notification(self, notification_id: int) -> Notification | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
        return self._row_to_notification(row) if row else None

    def mark_read(self, notification_id: int) -> None:
        with self.connection() as conn:
            conn.execute("UPDATE notifications SET state = 'read' WHERE id = ?", (notification_id,))

    def delete_notification(self, notification_id: int) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))

    def bulk_delete_notifications(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self.connection() as conn:
            conn.execute(f"DELETE FROM notifications WHERE id IN ({placeholders})", ids)

    def clear_notifications_for_key(self, api_key: str) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM notifications WHERE api_key = ?", (api_key,))

    def clear_unassigned_notifications(self) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM notifications WHERE assignment_type = 'unassigned'")

    def list_audit_entries(self) -> list[AuditEntry]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC").fetchall()
        return [self._row_to_audit(row) for row in rows]

    def get_audit_entry(self, audit_id: int) -> AuditEntry | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM audit_log WHERE id = ?", (audit_id,)).fetchone()
        return self._row_to_audit(row) if row else None

    def list_key_summaries(self) -> list[KeySummary]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    k.api_key AS api_key,
                    COUNT(n.id) AS total_count,
                    SUM(CASE WHEN n.state = 'new' THEN 1 ELSE 0 END) AS new_count,
                    SUM(CASE WHEN n.state = 'read' THEN 1 ELSE 0 END) AS read_count
                FROM api_keys k
                LEFT JOIN notifications n ON n.api_key = k.api_key
                GROUP BY k.api_key
                ORDER BY k.api_key
                """
            ).fetchall()
        return [
            KeySummary(
                api_key=row["api_key"],
                total_count=row["total_count"] or 0,
                new_count=row["new_count"] or 0,
                read_count=row["read_count"] or 0,
            )
            for row in rows
        ]

    def unassigned_summary(self) -> KeySummary:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(id) AS total_count,
                    SUM(CASE WHEN state = 'new' THEN 1 ELSE 0 END) AS new_count,
                    SUM(CASE WHEN state = 'read' THEN 1 ELSE 0 END) AS read_count
                FROM notifications
                WHERE assignment_type = 'unassigned'
                """
            ).fetchone()
        return KeySummary(
            api_key="__unassigned__",
            total_count=row["total_count"] or 0,
            new_count=row["new_count"] or 0,
            read_count=row["read_count"] or 0,
        )
