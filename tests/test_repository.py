from notifybridge.storage.repository import Repository


def test_repository_key_crud_and_counts(tmp_path):
    repo = Repository(tmp_path / "db.sqlite")
    repo.add_api_key("team-red")
    repo.add_api_key("team-blue")
    assert repo.list_api_keys() == ["team-blue", "team-red"]
    repo.set_api_key_enabled("team-blue", False)
    assert repo.has_api_key("team-blue") is False
    assert repo.has_api_key("team-red") is True

    first = repo.create_notification(
        api_key="team-red",
        source_ip="127.0.0.1",
        source_type="webhook",
        assignment_type="api_key",
        title="one",
        body="body",
        raw_payload="{}",
        metadata={},
    )
    second = repo.create_notification(
        api_key="team-red",
        source_ip=None,
        source_type="email",
        assignment_type="api_key",
        title="two",
        body="body",
        raw_payload="raw",
        metadata={},
        state="read",
    )
    repo.mark_read(first)
    summaries = {item.api_key: item for item in repo.list_key_summaries()}
    assert summaries["team-red"].total_count == 2
    assert summaries["team-red"].enabled is True
    assert summaries["team-red"].new_count == 0
    assert summaries["team-red"].read_count == 2
    assert summaries["team-blue"].total_count == 0
    assert summaries["team-blue"].enabled is False
    repo.delete_notification(second)
    remaining = repo.list_notifications("team-red")
    assert len(remaining) == 1
    assert remaining[0].source_ip == "127.0.0.1"


def test_repository_bulk_delete_clear_and_unassigned(tmp_path):
    repo = Repository(tmp_path / "db.sqlite")
    repo.add_api_key("team-red")
    one = repo.create_notification(
        api_key="team-red",
        source_ip="127.0.0.1",
        source_type="webhook",
        assignment_type="api_key",
        title="1",
        body="b",
        raw_payload="r",
        metadata={},
    )
    two = repo.create_notification(
        api_key=None,
        source_ip="127.0.0.2",
        source_type="syslog",
        assignment_type="unassigned",
        title="2",
        body="b",
        raw_payload="r",
        metadata={},
    )
    three = repo.create_notification(
        api_key="team-red",
        source_ip=None,
        source_type="email",
        assignment_type="api_key",
        title="3",
        body="b",
        raw_payload="r",
        metadata={},
    )
    repo.bulk_delete_notifications([one, two])
    remaining = repo.list_notifications()
    assert [item.id for item in remaining] == [three]
    assert repo.unassigned_summary().total_count == 0
    repo.clear_notifications_for_key("team-red")
    assert repo.list_notifications() == []


def test_repository_audit_log_persistence(tmp_path):
    repo = Repository(tmp_path / "db.sqlite")
    audit_id = repo.create_audit_entry(
        source_type="email",
        auth_status="missing_key",
        api_key_candidate=None,
        summary="Rejected email",
        raw_payload="raw",
        metadata={"to": "x"},
    )
    entry = repo.get_audit_entry(audit_id)
    assert entry is not None
    assert entry.auth_status == "missing_key"
    assert entry.metadata["to"] == "x"


def test_remove_api_key_cascades_notifications(tmp_path):
    repo = Repository(tmp_path / "db.sqlite")
    repo.add_api_key("team-red")
    repo.create_notification(
        api_key="team-red",
        source_ip="127.0.0.1",
        source_type="webhook",
        assignment_type="api_key",
        title="to be removed",
        body="body",
        raw_payload="{}",
        metadata={},
    )
    assert len(repo.list_notifications("team-red")) == 1
    repo.remove_api_key("team-red")
    assert repo.list_api_keys() == []
    assert repo.list_notifications("team-red") == []
