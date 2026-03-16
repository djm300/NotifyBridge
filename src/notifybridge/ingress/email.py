from __future__ import annotations

from notifybridge.core.ingestion import IngestionService


class SMTPHandler:
    """SMTP adapter contract that forwards raw messages into shared ingestion."""

    def __init__(self, ingestion: IngestionService) -> None:
        """Create the SMTP handler.

        Inputs:
        - `ingestion`: shared ingestion service.

        Outputs:
        - Adapter instance suitable for `aiosmtpd.Controller`.
        """
        self.ingestion = ingestion

    async def handle_DATA(self, server, session, envelope):
        """Receive one SMTP DATA payload.

        Inputs:
        - `server`, `session`: `aiosmtpd` callback arguments, unused here.
        - `envelope`: object carrying `original_content`.

        Outputs:
        - SMTP success string after forwarding the raw message to ingestion.
        """
        await self.ingestion.ingest_email(envelope.original_content)
        return "250 Message accepted"
