from __future__ import annotations

from typing import Any

from notifybridge.core.events import EventBus
from notifybridge.core.models import IngestResult
from notifybridge.core.normalization import (
    extract_email_auth_candidate,
    extract_syslog_auth,
    normalize_email,
    normalize_syslog,
    normalize_webhook,
)
from notifybridge.storage.repository import Repository


class IngestionService:
    def __init__(self, repository: Repository, event_bus: EventBus, email_domain: str) -> None:
        self.repository = repository
        self.event_bus = event_bus
        self.email_domain = email_domain

    async def ingest_webhook(self, api_key: str, payload: Any, remote_addr: str = "") -> IngestResult:
        if not self.repository.has_api_key(api_key):
            audit_id = self.repository.create_audit_entry(
                source_type="webhook",
                auth_status="unknown_key",
                api_key_candidate=api_key,
                summary="Rejected webhook with unknown API key",
                raw_payload=str(payload),
                metadata={"remote_addr": remote_addr},
            )
            return IngestResult(False, None, audit_id, None, "unknown_key")

        title, body, raw_payload, metadata = normalize_webhook(payload)
        notification_id = self.repository.create_notification(
            api_key=api_key,
            source_type="webhook",
            assignment_type="api_key",
            title=title,
            body=body,
            raw_payload=raw_payload,
            metadata={**metadata, "remote_addr": remote_addr},
        )
        audit_id = self.repository.create_audit_entry(
            source_type="webhook",
            auth_status="accepted",
            api_key_candidate=api_key,
            summary=title,
            raw_payload=raw_payload,
            metadata={"remote_addr": remote_addr},
        )
        await self.event_bus.publish("notification.created", {"id": notification_id, "bucket": api_key})
        return IngestResult(True, notification_id, audit_id, api_key, "accepted")

    async def ingest_email(self, raw_message: bytes) -> IngestResult:
        api_key, to_header = extract_email_auth_candidate(raw_message, self.email_domain)
        if not self.repository.has_api_key(api_key):
            audit_id = self.repository.create_audit_entry(
                source_type="email",
                auth_status="unknown_key" if api_key else "missing_key",
                api_key_candidate=api_key,
                summary="Rejected email",
                raw_payload=raw_message.decode("utf-8", errors="replace"),
                metadata={"to": to_header},
            )
            return IngestResult(False, None, audit_id, None, "unknown_key" if api_key else "missing_key")

        title, body, raw_payload, metadata = normalize_email(raw_message)
        notification_id = self.repository.create_notification(
            api_key=api_key,
            source_type="email",
            assignment_type="api_key",
            title=title,
            body=body,
            raw_payload=raw_payload,
            metadata=metadata,
        )
        audit_id = self.repository.create_audit_entry(
            source_type="email",
            auth_status="accepted",
            api_key_candidate=api_key,
            summary=title,
            raw_payload=raw_payload,
            metadata=metadata,
        )
        await self.event_bus.publish("notification.created", {"id": notification_id, "bucket": api_key})
        return IngestResult(True, notification_id, audit_id, api_key, "accepted")

    async def ingest_syslog(self, line: str, remote_addr: str = "") -> IngestResult:
        api_key, auth_metadata = extract_syslog_auth(line)
        has_key = self.repository.has_api_key(api_key)
        permissive = self.repository.get_syslog_mode() == "permissive"

        if not has_key and not permissive:
            audit_id = self.repository.create_audit_entry(
                source_type="syslog",
                auth_status="unknown_key" if api_key else "missing_key",
                api_key_candidate=api_key,
                summary="Rejected syslog",
                raw_payload=line,
                metadata={**auth_metadata, "remote_addr": remote_addr},
            )
            return IngestResult(False, None, audit_id, None, "unknown_key" if api_key else "missing_key")

        title, body, raw_payload, metadata = normalize_syslog(line)
        bucket = api_key if has_key else "__unassigned__"
        assignment_type = "api_key" if has_key else "unassigned"
        notification_id = self.repository.create_notification(
            api_key=api_key if has_key else None,
            source_type="syslog",
            assignment_type=assignment_type,
            title=title,
            body=body,
            raw_payload=raw_payload,
            metadata={**metadata, **auth_metadata, "remote_addr": remote_addr},
        )
        audit_id = self.repository.create_audit_entry(
            source_type="syslog",
            auth_status="accepted" if has_key else "accepted_unassigned",
            api_key_candidate=api_key,
            summary=title,
            raw_payload=raw_payload,
            metadata={**auth_metadata, "remote_addr": remote_addr},
        )
        await self.event_bus.publish("notification.created", {"id": notification_id, "bucket": bucket})
        return IngestResult(True, notification_id, audit_id, bucket, "accepted")
