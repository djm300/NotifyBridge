from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Notification:
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
    api_key: str
    total_count: int
    new_count: int
    read_count: int


@dataclass(slots=True)
class IngestResult:
    accepted: bool
    notification_id: int | None
    audit_id: int
    bucket: str | None
    reason: str
