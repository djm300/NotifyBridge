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
    """Shared ingress decision engine for webhook, email, and syslog."""

    def __init__(self, repository: Repository, event_bus: EventBus, email_domain: str) -> None:
        """Create the ingestion service.

        Inputs:
        - `repository`: persistence layer for notifications and audit records.
        - `event_bus`: in-process pub/sub bus for UI updates.
        - `email_domain`: accepted local domain for `To:`-based email auth.

        Outputs:
        - Ready-to-use ingestion service instance.
        """
        self.repository = repository
        self.event_bus = event_bus
        self.email_domain = email_domain

    async def _reject(
        self,
        *,
        source_type: str,
        auth_status: str,
        api_key_candidate: str | None,
        summary: str,
        raw_payload: str,
        metadata: dict[str, Any],
        reason: str,
    ) -> IngestResult:
        """Create a rejected audit result without notification persistence.

        Inputs:
        - Rejection metadata, audit fields, and the externally visible reason code.

        Outputs:
        - `IngestResult` for a rejected ingress attempt.
        """
        audit_id = self.repository.create_audit_entry(
            source_type=source_type,
            auth_status=auth_status,
            api_key_candidate=api_key_candidate,
            summary=summary,
            raw_payload=raw_payload,
            metadata=metadata,
        )
        return IngestResult(False, None, audit_id, None, reason)

    async def _accept(
        self,
        *,
        source_type: str,
        api_key_candidate: str | None,
        source_ip: str | None,
        assignment_type: str,
        bucket: str,
        title: str,
        body: str,
        raw_payload: str,
        notification_metadata: dict[str, Any],
        audit_status: str,
        audit_metadata: dict[str, Any],
    ) -> IngestResult:
        """Persist an accepted notification, write audit history, and publish an event.

        Inputs:
        - Notification fields, audit fields, bucket name, and assignment type.

        Outputs:
        - `IngestResult` for an accepted ingress attempt.
        """
        notification_id = self.repository.create_notification(
            api_key=api_key_candidate if assignment_type == "api_key" else None,
            source_ip=source_ip,
            source_type=source_type,
            assignment_type=assignment_type,
            title=title,
            body=body,
            raw_payload=raw_payload,
            metadata=notification_metadata,
        )
        audit_id = self.repository.create_audit_entry(
            source_type=source_type,
            auth_status=audit_status,
            api_key_candidate=api_key_candidate,
            summary=title,
            raw_payload=raw_payload,
            metadata=audit_metadata,
        )
        await self.event_bus.publish("notification.created", {"id": notification_id, "bucket": bucket})
        return IngestResult(True, notification_id, audit_id, bucket, "accepted")

    async def ingest_webhook(self, api_key: str, payload: Any, remote_addr: str = "") -> IngestResult:
        """Handle one webhook payload.

        Inputs:
        - `api_key`: key extracted from the request path.
        - `payload`: decoded webhook body.
        - `remote_addr`: client IP when available.

        Outputs:
        - `IngestResult` describing acceptance, audit entry, and bucket routing.
        """
        if not self.repository.has_api_key(api_key):
            return await self._reject(
                source_type="webhook",
                auth_status="unknown_key",
                api_key_candidate=api_key,
                summary="Rejected webhook with unknown API key",
                raw_payload=str(payload),
                metadata={"remote_addr": remote_addr},
                reason="unknown_key",
            )

        title, body, raw_payload, metadata = normalize_webhook(payload)
        return await self._accept(
            source_type="webhook",
            api_key_candidate=api_key,
            source_ip=remote_addr or None,
            assignment_type="api_key",
            bucket=api_key,
            title=title,
            body=body,
            raw_payload=raw_payload,
            notification_metadata={**metadata, "remote_addr": remote_addr},
            audit_status="accepted",
            audit_metadata={"remote_addr": remote_addr},
        )

    async def ingest_email(self, raw_message: bytes, remote_addr: str = "") -> IngestResult:
        """Handle one raw email.

        Inputs:
        - `raw_message`: RFC 2822 message bytes.
        - `remote_addr`: SMTP client IP when available.

        Outputs:
        - `IngestResult` describing acceptance, audit entry, and bucket routing.
        """
        api_key, to_header = extract_email_auth_candidate(raw_message, self.email_domain)
        if not self.repository.has_api_key(api_key):
            return await self._reject(
                source_type="email",
                auth_status="unknown_key" if api_key else "missing_key",
                api_key_candidate=api_key,
                summary="Rejected email",
                raw_payload=raw_message.decode("utf-8", errors="replace"),
                metadata={"to": to_header},
                reason="unknown_key" if api_key else "missing_key",
            )

        title, body, raw_payload, metadata = normalize_email(raw_message)
        return await self._accept(
            source_type="email",
            api_key_candidate=api_key,
            source_ip=remote_addr or None,
            assignment_type="api_key",
            bucket=api_key,
            title=title,
            body=body,
            raw_payload=raw_payload,
            notification_metadata=metadata,
            audit_status="accepted",
            audit_metadata=metadata,
        )

    async def ingest_syslog(self, line: str, remote_addr: str = "") -> IngestResult:
        """Handle one syslog line.

        Inputs:
        - `line`: decoded syslog line.
        - `remote_addr`: sender IP when available.

        Outputs:
        - `IngestResult` describing acceptance, audit entry, and bucket routing.
        """
        api_key, auth_metadata = extract_syslog_auth(line)
        has_key = self.repository.has_api_key(api_key)
        permissive = self.repository.get_syslog_mode() == "permissive"
        audit_metadata = {**auth_metadata, "remote_addr": remote_addr}

        if not has_key and not permissive:
            return await self._reject(
                source_type="syslog",
                auth_status="unknown_key" if api_key else "missing_key",
                api_key_candidate=api_key,
                summary="Rejected syslog",
                raw_payload=line,
                metadata=audit_metadata,
                reason="unknown_key" if api_key else "missing_key",
            )

        title, body, raw_payload, metadata = normalize_syslog(line)
        bucket = api_key if has_key else "__unassigned__"
        assignment_type = "api_key" if has_key else "unassigned"
        return await self._accept(
            source_type="syslog",
            api_key_candidate=api_key,
            source_ip=remote_addr or None,
            assignment_type=assignment_type,
            bucket=bucket,
            title=title,
            body=body,
            raw_payload=raw_payload,
            notification_metadata={**metadata, **audit_metadata},
            audit_status="accepted" if has_key else "accepted_unassigned",
            audit_metadata=audit_metadata,
        )
