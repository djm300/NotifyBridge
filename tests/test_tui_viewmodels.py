from notifybridge.logging_utils import LogEntry
from notifybridge.storage.repository import Repository
from notifybridge.tui.viewmodels import build_tui_state


def test_build_tui_state(tmp_path):
    repo = Repository(tmp_path / "db.sqlite")
    repo.add_api_key("team-red")
    repo.create_notification(
        api_key="team-red",
        source_type="webhook",
        assignment_type="api_key",
        title="Build done",
        body="ok",
        raw_payload="{}",
        metadata={},
    )
    repo.set_syslog_mode(True)
    repo.create_notification(
        api_key=None,
        source_type="syslog",
        assignment_type="unassigned",
        title="orphan",
        body="body",
        raw_payload="raw",
        metadata={},
    )
    state = build_tui_state(repo, [LogEntry(level="INFO", message="started")])
    assert any("team-red" in line for line in state.keys)
    assert any("unassigned-syslog" in line for line in state.keys)
    assert any("Build done" in line for line in state.messages)
    assert state.logs == ["started"]
