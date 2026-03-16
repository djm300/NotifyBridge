from __future__ import annotations

from email import policy
from email.parser import BytesHeaderParser, BytesParser
import json
from typing import Any


def normalize_webhook(payload: Any) -> tuple[str, str, str, dict[str, Any]]:
    """Normalize a webhook payload into notification fields.

    Inputs:
    - `payload`: arbitrary webhook body, typically dict or string.

    Outputs:
    - `(title, body, raw_payload, metadata)` for notification persistence.
    """
    raw_payload = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    if isinstance(payload, dict):
        title = str(payload.get("title") or "Webhook message")
        body = str(payload.get("body") or payload.get("message") or raw_payload)
        metadata = {"keys": sorted(payload.keys())}
    else:
        title = "Webhook message"
        body = str(payload)
        metadata = {}
    return title, body, raw_payload, metadata


def extract_email_auth_candidate(raw_message: bytes, domain: str) -> tuple[str | None, str]:
    """Extract the API key candidate from the primary email `To:` header.

    Inputs:
    - `raw_message`: raw RFC 2822 message bytes.
    - `domain`: accepted local email domain suffix.

    Outputs:
    - `(api_key_candidate, raw_to_header)`.
    """
    headers = BytesHeaderParser(policy=policy.default).parsebytes(raw_message)
    to_header = headers.get("To", "")
    candidate = None
    if "<" in to_header and ">" in to_header:
        address = to_header.split("<", 1)[1].split(">", 1)[0].strip()
    else:
        address = to_header.split(",", 1)[0].strip()
    expected_suffix = f"@{domain}"
    if address.endswith(expected_suffix):
        candidate = address[: -len(expected_suffix)]
    return candidate, to_header


def normalize_email(raw_message: bytes) -> tuple[str, str, str, dict[str, Any]]:
    """Normalize an email into notification fields.

    Inputs:
    - `raw_message`: raw RFC 2822 message bytes.

    Outputs:
    - `(title, body, raw_payload, metadata)` with attachments counted and stripped.
    """
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    title = message.get("Subject", "(no subject)")
    body = ""
    attachments = 0
    if message.is_multipart():
        parts: list[str] = []
        for part in message.walk():
            disposition = part.get_content_disposition()
            if disposition == "attachment":
                attachments += 1
                continue
            if part.get_content_type() == "text/plain":
                parts.append(part.get_content())
        body = "\n".join(part.strip() for part in parts if part.strip())
    else:
        body = message.get_content().strip()
    metadata = {
        "from": message.get("From", ""),
        "to": message.get("To", ""),
        "cc": message.get("Cc", ""),
        "attachments_stripped": attachments,
    }
    return title, body or "(empty body)", raw_message.decode("utf-8", errors="replace"), metadata


def extract_syslog_auth(line: str) -> tuple[str | None, dict[str, Any]]:
    """Extract a syslog API key candidate from structured data or fallback prefix.

    Inputs:
    - `line`: one decoded syslog line.

    Outputs:
    - `(api_key_candidate, metadata)` where metadata records which auth source matched.
    """
    metadata: dict[str, Any] = {}
    structured_marker = "[notifybridge@32473"
    if structured_marker in line and 'apiKey="' in line:
        try:
            segment = line.split(structured_marker, 1)[1].split("]", 1)[0]
            api_key = segment.split('apiKey="', 1)[1].split('"', 1)[0]
            metadata["auth_source"] = "structured_data"
            return api_key, metadata
        except IndexError:
            pass
    marker = "[nb:"
    if marker in line:
        try:
            api_key = line.split(marker, 1)[1].split("]", 1)[0]
            metadata["auth_source"] = "prefix"
            return api_key, metadata
        except IndexError:
            pass
    metadata["auth_source"] = "missing"
    return None, metadata


def normalize_syslog(line: str) -> tuple[str, str, str, dict[str, Any]]:
    """Normalize a syslog line into notification fields.

    Inputs:
    - `line`: one decoded syslog line.

    Outputs:
    - `(title, body, raw_payload, metadata)` for notification persistence.
    """
    body = line
    if "[nb:" in line and "]" in line:
        body = line.split("]", 1)[1].strip()
    title = body[:80] if body else "Syslog message"
    return title or "Syslog message", body or line, line, {}
