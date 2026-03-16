from __future__ import annotations

import asyncio

from notifybridge.core.ingestion import IngestionService


class SyslogProtocol(asyncio.DatagramProtocol):
    """UDP syslog adapter that forwards datagrams into shared ingestion.

    Why inheritance is used:
    - This inherits from `asyncio.DatagramProtocol` because asyncio UDP servers
      deliver received packets through protocol callbacks instead of plain functions.
    """

    def __init__(self, ingestion: IngestionService) -> None:
        """Create the syslog protocol adapter.

        Inputs:
        - `ingestion`: shared ingestion service.

        Outputs:
        - Protocol instance suitable for `create_datagram_endpoint`.
        """
        self.ingestion = ingestion

    def datagram_received(self, data: bytes, addr) -> None:
        """Handle one incoming UDP datagram.

        Inputs:
        - `data`: raw UDP payload.
        - `addr`: sender address tuple.

        Outputs:
        - Schedules one async syslog ingestion task.
        """
        line = data.decode("utf-8", errors="replace").strip()
        asyncio.create_task(self.ingestion.ingest_syslog(line, addr[0] if addr else ""))
