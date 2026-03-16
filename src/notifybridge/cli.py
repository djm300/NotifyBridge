from __future__ import annotations

import argparse
import asyncio
import threading
import time

from aiosmtpd.controller import Controller
import uvicorn

from notifybridge.api.app import create_app
from notifybridge.config import load_settings
from notifybridge.ingress.email import SMTPHandler
from notifybridge.ingress.syslog import SyslogProtocol
from notifybridge.runtime import build_runtime
from notifybridge.tui.app import NotifyBridgeTUI


def _start_syslog_server(runtime):
    """Start the UDP syslog listener on a dedicated event loop.

    Inputs:
    - `runtime`: shared runtime used to obtain settings and ingestion service.

    Outputs:
    - Runs a long-lived UDP server loop until process shutdown.
    """
    async def runner():
        """Run the background UDP server forever.

        Inputs:
        - None, closes over `runtime`.

        Outputs:
        - Keeps the UDP listener alive until shutdown.
        """
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: SyslogProtocol(runtime.ingestion),
            local_addr=(runtime.settings.syslog_host, runtime.settings.syslog_port),
        )
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            transport.close()

    asyncio.run(runner())


def dev_command() -> int:
    """Start the full local development stack.

    Inputs:
    - None. Reads config from the environment via `load_settings`.

    Outputs:
    - Starts web, SMTP, syslog, and TUI services and returns process exit code.
    """
    settings = load_settings()
    runtime = build_runtime(settings)
    runtime.logger.info("Starting NotifyBridge")

    smtp = Controller(
        SMTPHandler(runtime.ingestion),
        hostname=settings.smtp_host,
        port=settings.smtp_port,
    )
    smtp.start()

    syslog_thread = threading.Thread(target=_start_syslog_server, args=(runtime,), daemon=True)
    syslog_thread.start()

    app = create_app(runtime)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=settings.http_host,
            port=settings.http_port,
            log_level="warning",
        )
    )
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    runtime.logger.info(
        "NotifyBridge listening on http://%s:%s, smtp %s, syslog %s",
        settings.http_host,
        settings.http_port,
        settings.smtp_port,
        settings.syslog_port,
    )

    if getattr(__import__("sys"), "stdout").isatty():
        tui = NotifyBridgeTUI(runtime)
        try:
            tui.run()
        finally:
            smtp.stop()
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            smtp.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Inputs:
    - `argv`: optional argv override for tests or embedded execution.

    Outputs:
    - Integer process exit code.
    """
    parser = argparse.ArgumentParser(prog="notifybridge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("dev")
    args = parser.parse_args(argv)
    if args.command == "dev":
        return dev_command()
    return 1
