from notifybridge.core.events import EventBus
from notifybridge.core.ingestion import IngestionService
from notifybridge.storage.repository import Repository


def make_service(tmp_path):
    repo = Repository(tmp_path / "db.sqlite")
    bus = EventBus()
    service = IngestionService(repo, bus, "notifybridge.local")
    return repo, service


async def test_webhook_rejects_unknown_key(tmp_path):
    repo, service = make_service(tmp_path)
    result = await service.ingest_webhook("missing", {"title": "hello"})
    assert result.accepted is False
    assert repo.list_notifications() == []
    assert repo.list_audit_entries()[0].auth_status == "unknown_key"


async def test_webhook_rejects_disabled_key(tmp_path):
    repo, service = make_service(tmp_path)
    repo.add_api_key("team-red")
    repo.set_api_key_enabled("team-red", False)
    result = await service.ingest_webhook("team-red", {"title": "hello"})
    assert result.accepted is False
    assert repo.list_notifications() == []
    assert repo.list_audit_entries()[0].auth_status == "unknown_key"


async def test_email_accepts_primary_to_and_strips_attachments(tmp_path):
    repo, service = make_service(tmp_path)
    repo.add_api_key("team-red")
    raw = (
        b"From: alerts@example.test\r\n"
        b"To: team-red@notifybridge.local\r\n"
        b"Subject: Disk warning\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=abc\r\n\r\n"
        b"--abc\r\nContent-Type: text/plain\r\n\r\nhello world\r\n"
        b"--abc\r\nContent-Type: text/plain\r\nContent-Disposition: attachment; filename=test.txt\r\n\r\nignored\r\n--abc--\r\n"
    )
    result = await service.ingest_email(raw)
    assert result.accepted is True
    item = repo.list_notifications("team-red")[0]
    assert item.title == "Disk warning"
    assert item.metadata["attachments_stripped"] == 1


async def test_email_rejects_cc_only_match(tmp_path):
    repo, service = make_service(tmp_path)
    repo.add_api_key("team-red")
    raw = (
        b"From: alerts@example.test\r\n"
        b"To: hello@notifybridge.local\r\n"
        b"Cc: team-red@notifybridge.local\r\n"
        b"Subject: Disk warning\r\n\r\nbody\r\n"
    )
    result = await service.ingest_email(raw)
    assert result.accepted is False
    assert repo.list_notifications() == []


async def test_syslog_strict_and_permissive_modes(tmp_path):
    repo, service = make_service(tmp_path)
    repo.add_api_key("team-red")
    strict = await service.ingest_syslog("<134> host backup failed")
    assert strict.accepted is False

    repo.set_syslog_mode(True)
    permissive = await service.ingest_syslog("<134> host backup failed")
    assert permissive.accepted is True
    item = repo.list_notifications(assignment_type="unassigned")[0]
    assert item.assignment_type == "unassigned"


async def test_syslog_accepts_structured_data_and_prefix(tmp_path):
    repo, service = make_service(tmp_path)
    repo.add_api_key("team-red")
    structured = await service.ingest_syslog(
        '<134>1 2026-03-16T20:00:00Z app notifybridge 1 ID47 [notifybridge@32473 apiKey="team-red"] backup failed'
    )
    prefixed = await service.ingest_syslog("<134>Mar 16 20:00:00 host [nb:team-red] backup failed")
    assert structured.accepted is True
    assert prefixed.accepted is True
    assert len(repo.list_notifications("team-red")) == 2
