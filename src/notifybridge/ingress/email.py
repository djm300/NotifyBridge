from __future__ import annotations

from notifybridge.core.ingestion import IngestionService


class SMTPHandler:
    def __init__(self, ingestion: IngestionService) -> None:
        self.ingestion = ingestion

    async def handle_DATA(self, server, session, envelope):
        await self.ingestion.ingest_email(envelope.original_content)
        return "250 Message accepted"
