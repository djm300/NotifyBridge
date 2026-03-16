import asyncio

from notifybridge.ingress.email import SMTPHandler
from notifybridge.ingress.syslog import SyslogProtocol


class DummyIngestion:
    def __init__(self):
        self.calls = []

    async def ingest_email(self, payload):
        self.calls.append(("email", payload))

    async def ingest_syslog(self, payload, remote_addr=""):
        self.calls.append(("syslog", payload, remote_addr))


class DummyEnvelope:
    def __init__(self, content: bytes):
        self.original_content = content


async def test_smtp_handler_forwards_raw_message():
    ingestion = DummyIngestion()
    handler = SMTPHandler(ingestion)
    result = await handler.handle_DATA(None, None, DummyEnvelope(b"hello"))
    assert result == "250 Message accepted"
    assert ingestion.calls == [("email", b"hello")]


async def test_syslog_protocol_forwards_datagram():
    ingestion = DummyIngestion()
    protocol = SyslogProtocol(ingestion)
    protocol.datagram_received(b"<134> test message", ("127.0.0.1", 9999))
    await asyncio.sleep(0)
    assert ingestion.calls == [("syslog", "<134> test message", "127.0.0.1")]
