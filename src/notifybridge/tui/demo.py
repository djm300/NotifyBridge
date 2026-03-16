from __future__ import annotations

import asyncio
from email.message import EmailMessage
import http.client
import json
import smtplib
import socket

from notifybridge.config import Settings
from notifybridge.core.keys import generate_api_key


def generate_demo_keys(count: int = 5) -> list[str]:
    """Generate demo API keys for sample traffic.

    Inputs:
    - `count`: number of keys to generate.

    Outputs:
    - List of random key strings suitable for local demo usage.
    """
    return [generate_api_key(20) for _ in range(count)]


def post_key(settings: Settings) -> str:
    """Create one API key through the local HTTP API.

    Inputs:
    - `settings`: runtime settings containing localhost HTTP target.

    Outputs:
    - Sends one localhost HTTP request and returns the generated key.
    """
    conn = http.client.HTTPConnection(settings.http_host, settings.http_port, timeout=5)
    try:
        conn.request("POST", "/api/keys", body="{}", headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        if response.status not in {200, 201}:
            raise RuntimeError(f"Failed to create key: HTTP {response.status}")
        return data["api_key"]
    finally:
        conn.close()


def send_webhook(settings: Settings, api_key: str, channel_index: int) -> None:
    """Send one demo webhook over localhost.

    Inputs:
    - `settings`: runtime settings containing localhost HTTP target.
    - `api_key`: destination API key.
    - `channel_index`: demo sequence number used in the payload.

    Outputs:
    - Sends one localhost webhook request.
    """
    conn = http.client.HTTPConnection(settings.http_host, settings.http_port, timeout=5)
    try:
        payload = {
            "title": f"Webhook demo {channel_index}",
            "body": f"demo webhook for {api_key}",
        }
        conn.request(
            "POST",
            f"/ingest/webhook/{api_key}",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        response.read()
        if response.status not in {201, 202}:
            raise RuntimeError(f"Webhook failed for {api_key}: HTTP {response.status}")
    finally:
        conn.close()


def send_email(settings: Settings, api_key: str, channel_index: int) -> None:
    """Send one demo email over localhost SMTP.

    Inputs:
    - `settings`: runtime settings containing localhost SMTP target and email domain.
    - `api_key`: destination API key.
    - `channel_index`: demo sequence number used in the message.

    Outputs:
    - Sends one RFC 2822 message through the local SMTP listener.
    """
    message = EmailMessage()
    message["From"] = "demo@localhost"
    message["To"] = f"{api_key}@{settings.email_domain}"
    message["Subject"] = f"Email demo {channel_index}"
    message.set_content(f"demo email for {api_key}")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
        smtp.send_message(message)


def send_syslog(settings: Settings, api_key: str, channel_index: int) -> None:
    """Send one demo syslog datagram over localhost UDP.

    Inputs:
    - `settings`: runtime settings containing localhost UDP target.
    - `api_key`: destination API key.
    - `channel_index`: demo sequence number used in the message.

    Outputs:
    - Sends one localhost syslog UDP datagram.
    """
    payload = f'<134>Mar 16 20:00:0{channel_index} localhost [nb:{api_key}] demo syslog for {api_key}'
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload.encode("utf-8"), (settings.syslog_host, settings.syslog_port))


async def seed_random_demo(settings: Settings, count: int = 5) -> list[str]:
    """Create demo keys and send demo traffic over all localhost channels.

    Inputs:
    - `settings`: runtime settings for localhost HTTP, SMTP, UDP, and email domain.
    - `count`: number of demo keys to generate.

    Outputs:
    - List of created demo keys after all localhost traffic has been sent.
    """
    _ = generate_demo_keys(count)
    keys: list[str] = []
    for index in range(1, count + 1):
        api_key = await asyncio.to_thread(post_key, settings)
        keys.append(api_key)
        await asyncio.to_thread(send_webhook, settings, api_key, index)
        await asyncio.to_thread(send_email, settings, api_key, index)
        await asyncio.to_thread(send_syslog, settings, api_key, index)
    return keys
