from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, Static

from notifybridge.runtime import Runtime
from notifybridge.tui.viewmodels import build_tui_state


class NotifyBridgeTUI(App[None]):
    """Read-only Textual application for live operator visibility.

    Why inheritance is used:
    - This inherits from `textual.app.App` because Textual applications are
      defined by subclassing the framework base class and overriding lifecycle hooks.
    """

    CSS = """
    Screen { background: #0f172a; color: #e5eefb; }
    #layout { height: 1fr; }
    .pane {
      border: solid #38bdf8;
      padding: 1;
      width: 1fr;
      content-align: left top;
    }
    #command-bar {
      dock: bottom;
      margin: 1 0 0 0;
    }
    #status {
      dock: bottom;
      color: #9fb3c8;
      padding: 0 1;
    }
    """

    def __init__(self, runtime: Runtime) -> None:
        """Create the TUI app.

        Inputs:
        - `runtime`: shared runtime used to read logs and persisted state.

        Outputs:
        - Configured Textual app instance.
        """
        super().__init__()
        self.runtime = runtime

    def compose(self) -> ComposeResult:
        """Declare the TUI layout.

        Inputs:
        - None.

        Outputs:
        - Textual widgets for the three main panes and header/footer.
        """
        yield Header(show_clock=True)
        with Horizontal(id="layout"):
            yield Static(id="logs", classes="pane")
            yield Static(id="keys", classes="pane")
            yield Static(id="messages", classes="pane")
        yield Static("Commands: /q or /e to exit", id="status")
        yield Input(placeholder="/q or /e", id="command-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Start periodic pane refresh after the app mounts.

        Inputs:
        - None.

        Outputs:
        - Registers a refresh timer and paints the initial state.
        """
        self.set_interval(1.0, self.refresh_panes)
        self.refresh_panes()
        self.query_one("#command-bar", Input).focus()

    def handle_command(self, command: str) -> str:
        """Execute one slash command entered in the TUI.

        Inputs:
        - `command`: raw command text from the command bar.

        Outputs:
        - A status string: `exit`, `noop`, or `unknown`.
        """
        normalized = command.strip().lower()
        if not normalized:
            return "noop"
        if normalized in {"/q", "/e"}:
            return "exit"
        return "unknown"

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle slash command submission from the command bar.

        Inputs:
        - `event`: Textual input submission event.

        Outputs:
        - Executes the command, updates status text, and may exit the app.
        """
        result = self.handle_command(event.value)
        input_widget = self.query_one("#command-bar", Input)
        status_widget = self.query_one("#status", Static)
        input_widget.value = ""
        if result == "exit":
            status_widget.update("Exiting NotifyBridge TUI")
            self.exit()
            return
        if result == "noop":
            status_widget.update("Commands: /q or /e to exit")
            return
        status_widget.update(f"Unknown command: {event.value}")

    def refresh_panes(self) -> None:
        """Rebuild and repaint all TUI panes.

        Inputs:
        - None.

        Outputs:
        - Updates log, key, and message widgets with current data.
        """
        state = build_tui_state(self.runtime.repository, self.runtime.log_buffer.snapshot())
        self.query_one("#logs", Static).update("Logs\n\n" + "\n".join(state.logs or ["(no logs)"]))
        self.query_one("#keys", Static).update("Keys\n\n" + "\n".join(state.keys or ["(no keys)"]))
        self.query_one("#messages", Static).update("Messages\n\n" + "\n".join(state.messages or ["(no messages)"]))
