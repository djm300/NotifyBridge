from notifybridge.config import load_settings
from notifybridge.runtime import build_runtime
from notifybridge.tui.app import NotifyBridgeTUI


def make_app(tmp_path):
    settings = load_settings()
    settings.sqlite_path = tmp_path / "db.sqlite"
    runtime = build_runtime(settings)
    runtime.repository.add_api_key("team-red")
    runtime.repository.create_notification(
        api_key="team-red",
        source_type="webhook",
        assignment_type="api_key",
        title="hello",
        body="world",
        raw_payload="{}",
        metadata={},
    )
    return NotifyBridgeTUI(runtime), runtime


def test_tui_exit_commands(tmp_path):
    app, _runtime = make_app(tmp_path)
    assert app.handle_command("/q") == "exit"
    assert app.handle_command("/e") == "exit"


def test_tui_unknown_command(tmp_path):
    app, _runtime = make_app(tmp_path)
    assert app.handle_command("/what") == "unknown"
    assert app.handle_command("") == "noop"
    assert app.handle_command("/c") == "unknown"
    assert app.handle_command("/random") == "unknown"
