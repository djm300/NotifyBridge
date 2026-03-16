from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Notification:
    """Normalized notification record contract stored in SQLite and returned by APIs.

    Why the decorator is used:
    - `@dataclass` is used because this is a pure data carrier shared across
      storage, API serialization, and tests.
    """
    id: int | None
    received_at: str
    api_key: str | None
    source_type: str
    assignment_type: str
    state: str
    title: str
    body: str
    raw_payload: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuditEntry:
    """Audit event contract for accepted and rejected ingress attempts.

    Why the decorator is used:
    - `@dataclass` is used because audit entries are structured records without
      custom runtime behavior.
    """
    id: int | None
    received_at: str
    source_type: str
    auth_status: str
    api_key_candidate: str | None
    summary: str
    raw_payload: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class KeySummary:
    """Per-key count summary contract used by web and TUI views.

    Why the decorator is used:
    - `@dataclass` is used because this is a simple aggregate result from the repository.
    """
    api_key: str
    enabled: bool
    total_count: int
    new_count: int
    read_count: int


@dataclass(slots=True)
class IngestResult:
    """Result contract returned by ingestion operations.

    Why the decorator is used:
    - `@dataclass` is used because ingestion returns a structured result object
      that is passed directly to API serialization and tests.
    """
    accepted: bool
    notification_id: int | None
    audit_id: int
    bucket: str | None
    reason: str
