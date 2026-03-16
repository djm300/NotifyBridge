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
    """Return the current UTC timestamp as an ISO-8601 string.

    Inputs:
    - None.

    Outputs:
    - Timestamp string suitable for persistence.
    """
    return datetime.now(UTC).isoformat()


class Repository:
    """SQLite persistence contract for keys, notifications, audit log, and settings."""

    def __init__(self, path: Path | str) -> None:
        """Open or create the application database.

        Inputs:
        - `path`: filesystem path to the SQLite database file.

        Outputs:
        - Repository instance with schema initialized.
        """
        self.path = str(path)
        self._ensure_db()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Provide a committing SQLite connection scope.

        Inputs:
        - None.

        Outputs:
        - Yields an open `sqlite3.Connection` and commits on successful exit.

        Why the decorator is used:
        - `@contextmanager` lets callers use `with` syntax so connection lifecycle,
          commit behavior, and cleanup stay centralized in one place.
        """
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_db(self) -> None:
        """Initialize schema for the configured database.

        Inputs:
        - None.

        Outputs:
        - Ensures all required tables exist.
        """
        with self.connection() as conn:
            init_db(conn)

    def add_api_key(self, api_key: str) -> None:
        """Persist one API key.

        Inputs:
        - `api_key`: logical key identifier.

        Outputs:
        - Inserts the key if it does not already exist.
        """
        with self.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO api_keys(api_key) VALUES (?)", (api_key,))

    def remove_api_key(self, api_key: str) -> None:
        """Delete one API key.

        Inputs:
        - `api_key`: logical key identifier.

        Outputs:
        - Removes the key record and any notifications stored under that key.
        """
        with self.connection() as conn:
            conn.execute("DELETE FROM notifications WHERE api_key = ?", (api_key,))
            conn.execute("DELETE FROM api_keys WHERE api_key = ?", (api_key,))

    def set_api_key_enabled(self, api_key: str, enabled: bool) -> None:
        """Enable or disable one API key.

        Inputs:
        - `api_key`: logical key identifier.
        - `enabled`: target enabled state.

        Outputs:
        - Updates the stored enabled flag for the key.
        """
        with self.connection() as conn:
            conn.execute("UPDATE api_keys SET enabled = ? WHERE api_key = ?", (1 if enabled else 0, api_key))

    def list_api_keys(self) -> list[str]:
        """List configured API keys.

        Inputs:
        - None.

        Outputs:
        - Sorted list of API key strings.
        """
        with self.connection() as conn:
            rows = conn.execute("SELECT api_key FROM api_keys ORDER BY api_key").fetchall()
        return [row["api_key"] for row in rows]

    def has_api_key(self, api_key: str | None) -> bool:
        """Check whether one API key exists.

        Inputs:
        - `api_key`: candidate key string or `None`.

        Outputs:
        - `True` when the key exists, otherwise `False`.
        """
        if not api_key:
            return False
        with self.connection() as conn:
            row = conn.execute("SELECT 1 FROM api_keys WHERE api_key = ? AND enabled = 1", (api_key,)).fetchone()
        return row is not None

    def set_syslog_mode(self, permissive: bool) -> None:
        """Persist syslog strict/permissive mode.

        Inputs:
        - `permissive`: `True` for permissive mode, `False` for strict.

        Outputs:
        - Upserts the syslog mode setting.
        """
        value = "permissive" if permissive else "strict"
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES('syslog_mode', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (value,),
            )

    def get_syslog_mode(self) -> str:
        """Load the persisted syslog mode.

        Inputs:
        - None.

        Outputs:
        - `"strict"` or `"permissive"`.
        """
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
        """Insert one normalized notification.

        Inputs:
        - Notification persistence fields and metadata.

        Outputs:
        - The new notification ID.
        """
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
        """Insert one audit log record.

        Inputs:
        - Audit persistence fields and metadata.

        Outputs:
        - The new audit entry ID.
        """
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
        """Convert one SQLite row into a `Notification`.

        Inputs:
        - `row`: SQLite row from the notifications table.

        Outputs:
        - A populated `Notification` dataclass.
        """
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
        """Convert one SQLite row into an `AuditEntry`.

        Inputs:
        - `row`: SQLite row from the audit table.

        Outputs:
        - A populated `AuditEntry` dataclass.
        """
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
        """List notifications with optional filters.

        Inputs:
        - `api_key`: optional key filter.
        - `assignment_type`: optional assignment filter.

        Outputs:
        - Notifications ordered newest first.
        """
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
        """Fetch one notification by ID.

        Inputs:
        - `notification_id`: database notification ID.

        Outputs:
        - Matching `Notification` or `None`.
        """
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
        return self._row_to_notification(row) if row else None

    def mark_read(self, notification_id: int) -> None:
        """Mark one notification as read.

        Inputs:
        - `notification_id`: database notification ID.

        Outputs:
        - Updates persisted state to `read`.
        """
        with self.connection() as conn:
            conn.execute("UPDATE notifications SET state = 'read' WHERE id = ?", (notification_id,))

    def delete_notification(self, notification_id: int) -> None:
        """Delete one notification.

        Inputs:
        - `notification_id`: database notification ID.

        Outputs:
        - Removes the notification if present.
        """
        with self.connection() as conn:
            conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))

    def bulk_delete_notifications(self, ids: list[int]) -> None:
        """Delete multiple notifications by explicit ID list.

        Inputs:
        - `ids`: notification IDs to remove.

        Outputs:
        - Deletes all matching notifications.
        """
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self.connection() as conn:
            conn.execute(f"DELETE FROM notifications WHERE id IN ({placeholders})", ids)

    def clear_notifications_for_key(self, api_key: str) -> None:
        """Delete all notifications assigned to one API key.

        Inputs:
        - `api_key`: logical key identifier.

        Outputs:
        - Removes all notifications stored under that key.
        """
        with self.connection() as conn:
            conn.execute("DELETE FROM notifications WHERE api_key = ?", (api_key,))

    def clear_all_notifications(self) -> None:
        """Delete all stored notifications across all buckets.

        Inputs:
        - None.

        Outputs:
        - Removes every row from the notifications table.
        """
        with self.connection() as conn:
            conn.execute("DELETE FROM notifications")

    def clear_unassigned_notifications(self) -> None:
        """Delete all unassigned syslog notifications.

        Inputs:
        - None.

        Outputs:
        - Removes all `assignment_type = 'unassigned'` notifications.
        """
        with self.connection() as conn:
            conn.execute("DELETE FROM notifications WHERE assignment_type = 'unassigned'")

    def list_audit_entries(self) -> list[AuditEntry]:
        """List audit entries newest first.

        Inputs:
        - None.

        Outputs:
        - List of persisted `AuditEntry` records.
        """
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC").fetchall()
        return [self._row_to_audit(row) for row in rows]

    def get_audit_entry(self, audit_id: int) -> AuditEntry | None:
        """Fetch one audit entry by ID.

        Inputs:
        - `audit_id`: database audit entry ID.

        Outputs:
        - Matching `AuditEntry` or `None`.
        """
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM audit_log WHERE id = ?", (audit_id,)).fetchone()
        return self._row_to_audit(row) if row else None

    def list_key_summaries(self) -> list[KeySummary]:
        """Aggregate message counts for each configured API key.

        Inputs:
        - None.

        Outputs:
        - Sorted `KeySummary` records for all configured keys.
        """
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    k.api_key AS api_key,
                    k.enabled AS enabled,
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
                enabled=bool(row["enabled"]),
                total_count=row["total_count"] or 0,
                new_count=row["new_count"] or 0,
                read_count=row["read_count"] or 0,
            )
            for row in rows
        ]

    def unassigned_summary(self) -> KeySummary:
        """Aggregate message counts for the unassigned syslog bucket.

        Inputs:
        - None.

        Outputs:
        - One `KeySummary` representing unassigned notifications.
        """
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
            enabled=True,
            total_count=row["total_count"] or 0,
            new_count=row["new_count"] or 0,
            read_count=row["read_count"] or 0,
        )
