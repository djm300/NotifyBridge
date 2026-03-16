from __future__ import annotations

from contextlib import contextmanager
import http.client
import json
import socket
import smtplib
import threading
import time
from typing import Iterator

from aiosmtpd.controller import Controller
from email.message import EmailMessage
import uvicorn

from notifybridge.api.app import create_app
from notifybridge.config import load_settings
from notifybridge.ingress.email import SMTPHandler
from notifybridge.ingress.syslog import SyslogProtocol
from notifybridge.runtime import build_runtime


def find_free_port() -> int:
    """Reserve an ephemeral localhost TCP port number.

    Inputs:
    - None.

    Outputs:
    - An available port number for immediate reuse by a test listener.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_until(predicate, timeout: float = 5.0, interval: float = 0.05) -> None:
    """Poll until a condition becomes true or the timeout expires.

    Inputs:
    - `predicate`: zero-argument function returning truthy when the wait is complete.
    - `timeout`: maximum time to wait in seconds.
    - `interval`: sleep interval between polls in seconds.

    Outputs:
    - Returns when `predicate()` is truthy, otherwise raises `AssertionError`.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("Timed out waiting for condition")


class UvicornServerThread(threading.Thread):
    """Background thread contract for a real localhost HTTP server."""

    def __init__(self, runtime, host: str, port: int) -> None:
        """Create the HTTP server thread.

        Inputs:
        - `runtime`: application runtime used to build the FastAPI app.
        - `host`: bind host.
        - `port`: bind port.

        Outputs:
        - Thread instance that runs uvicorn until stopped.
        """
        super().__init__(daemon=True)
        self.server = uvicorn.Server(
            uvicorn.Config(
                create_app(runtime),
                host=host,
                port=port,
                log_level="warning",
            )
        )

    def run(self) -> None:
        """Run the uvicorn server in the thread.

        Inputs:
        - None.

        Outputs:
        - Serves HTTP until `should_exit` is set.
        """
        self.server.run()

    def stop(self) -> None:
        """Stop the running uvicorn server.

        Inputs:
        - None.

        Outputs:
        - Signals server shutdown and joins the thread.
        """
        self.server.should_exit = True
        self.join(timeout=5)


class SyslogServerThread(threading.Thread):
    """Background thread contract for a real localhost UDP syslog server."""

    def __init__(self, ingestion, host: str, port: int) -> None:
        """Create the UDP syslog server thread.

        Inputs:
        - `ingestion`: shared ingestion service.
        - `host`: bind host.
        - `port`: bind port.

        Outputs:
        - Thread instance that hosts an asyncio UDP endpoint.
        """
        super().__init__(daemon=True)
        self.ingestion = ingestion
        self.host = host
        self.port = port
        self.loop = None
        self.transport = None
        self.started = threading.Event()

    def run(self) -> None:
        """Run the UDP endpoint until explicitly stopped.

        Inputs:
        - None.

        Outputs:
        - Starts an asyncio event loop with one datagram endpoint.
        """
        import asyncio

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.transport, _ = self.loop.run_until_complete(
            self.loop.create_datagram_endpoint(
                lambda: SyslogProtocol(self.ingestion),
                local_addr=(self.host, self.port),
            )
        )
        self.started.set()
        self.loop.run_forever()
        if self.transport is not None:
            self.transport.close()
        self.loop.close()

    def stop(self) -> None:
        """Stop the UDP server thread.

        Inputs:
        - None.

        Outputs:
        - Closes the UDP transport and stops the loop.
        """
        if self.loop and self.transport:
            self.loop.call_soon_threadsafe(self.transport.close)
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.join(timeout=5)


@contextmanager
def running_stack(tmp_path) -> Iterator[tuple[object, object]]:
    """Start real localhost HTTP, SMTP, and UDP listeners for integration testing.

    Inputs:
    - `tmp_path`: pytest temp directory for SQLite persistence.

    Outputs:
    - Yields `(settings, runtime)` while all listeners are accepting socket traffic.
    """
    settings = load_settings()
    settings.sqlite_path = tmp_path / "db.sqlite"
    settings.http_host = "127.0.0.1"
    settings.smtp_host = "127.0.0.1"
    settings.syslog_host = "127.0.0.1"
    settings.http_port = find_free_port()
    settings.smtp_port = find_free_port()
    settings.syslog_port = find_free_port()
    runtime = build_runtime(settings)

    http_thread = UvicornServerThread(runtime, settings.http_host, settings.http_port)
    smtp_controller = Controller(SMTPHandler(runtime.ingestion), hostname=settings.smtp_host, port=settings.smtp_port)
    syslog_thread = SyslogServerThread(runtime.ingestion, settings.syslog_host, settings.syslog_port)

    http_thread.start()
    smtp_controller.start()
    syslog_thread.start()
    syslog_thread.started.wait(timeout=5)

    try:
        wait_until(lambda: _can_connect(settings.http_host, settings.http_port))
        yield settings, runtime
    finally:
        smtp_controller.stop()
        syslog_thread.stop()
        http_thread.stop()


def _can_connect(host: str, port: int) -> bool:
    """Check whether a TCP listener is accepting connections.

    Inputs:
    - `host`: localhost bind host.
    - `port`: TCP port.

    Outputs:
    - `True` if a connection succeeds, otherwise `False`.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def create_key_over_http(host: str, port: int) -> str:
    """Create one API key through the real HTTP socket.

    Inputs:
    - `host`: HTTP server host.
    - `port`: HTTP server port.

    Outputs:
    - Generated API key returned by the HTTP API.
    """
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request("POST", "/api/keys", body="{}", headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 201
        return payload["api_key"]
    finally:
        conn.close()


def test_webhook_over_real_http_socket(tmp_path):
    """Verify webhook ingestion through a real localhost HTTP socket.

    Inputs:
    - `tmp_path`: pytest temp directory.

    Outputs:
    - Asserts accepted webhook traffic persists as a notification.
    """
    with running_stack(tmp_path) as (settings, runtime):
        api_key = create_key_over_http(settings.http_host, settings.http_port)
        conn = http.client.HTTPConnection(settings.http_host, settings.http_port, timeout=5)
        try:
            conn.request(
                "POST",
                f"/ingest/webhook/{api_key}",
                body=json.dumps({"title": "Socket webhook", "body": "through http socket"}),
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            response.read()
            assert response.status == 201
        finally:
            conn.close()

        wait_until(lambda: len(runtime.repository.list_notifications(api_key)) == 1)
        item = runtime.repository.list_notifications(api_key)[0]
        assert item.title == "Socket webhook"


def test_email_over_real_smtp_socket(tmp_path):
    """Verify email ingestion through a real localhost SMTP socket.

    Inputs:
    - `tmp_path`: pytest temp directory.

    Outputs:
    - Asserts accepted SMTP traffic persists as a notification.
    """
    with running_stack(tmp_path) as (settings, runtime):
        api_key = create_key_over_http(settings.http_host, settings.http_port)

        message = EmailMessage()
        message["From"] = "alerts@example.test"
        message["To"] = f"{api_key}@{settings.email_domain}"
        message["Subject"] = "Socket SMTP"
        message.set_content("through smtp socket")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.send_message(message)

        wait_until(lambda: len(runtime.repository.list_notifications(api_key)) == 1)
        item = runtime.repository.list_notifications(api_key)[0]
        assert item.title == "Socket SMTP"
        assert item.source_type == "email"


def test_syslog_over_real_udp_socket(tmp_path):
    """Verify syslog ingestion through a real localhost UDP socket.

    Inputs:
    - `tmp_path`: pytest temp directory.

    Outputs:
    - Asserts accepted UDP syslog traffic persists as a notification.
    """
    with running_stack(tmp_path) as (settings, runtime):
        api_key = create_key_over_http(settings.http_host, settings.http_port)
        payload = f"<134>Mar 16 20:00:00 localhost [nb:{api_key}] through udp socket"

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(payload.encode("utf-8"), (settings.syslog_host, settings.syslog_port))

        wait_until(lambda: len(runtime.repository.list_notifications(api_key)) == 1)
        item = runtime.repository.list_notifications(api_key)[0]
        assert item.source_type == "syslog"
        assert "through udp socket" in item.body
