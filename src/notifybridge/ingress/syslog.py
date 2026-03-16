from __future__ import annotations

import asyncio

from notifybridge.core.ingestion import IngestionService


class SyslogProtocol(asyncio.DatagramProtocol):
    def __init__(self, ingestion: IngestionService) -> None:
        self.ingestion = ingestion

    def datagram_received(self, data: bytes, addr) -> None:
        line = data.decode("utf-8", errors="replace").strip()
        asyncio.create_task(self.ingestion.ingest_syslog(line, addr[0] if addr else ""))
