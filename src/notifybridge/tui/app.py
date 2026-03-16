from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from notifybridge.runtime import Runtime
from notifybridge.tui.viewmodels import build_tui_state


class NotifyBridgeTUI(App[None]):
    CSS = """
    Screen { background: #0f172a; color: #e5eefb; }
    #layout { height: 1fr; }
    .pane {
      border: solid #38bdf8;
      padding: 1;
      width: 1fr;
      content-align: left top;
    }
    """

    def __init__(self, runtime: Runtime) -> None:
        super().__init__()
        self.runtime = runtime

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="layout"):
            yield Static(id="logs", classes="pane")
            yield Static(id="keys", classes="pane")
            yield Static(id="messages", classes="pane")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_panes)
        self.refresh_panes()

    def refresh_panes(self) -> None:
        state = build_tui_state(self.runtime.repository, self.runtime.log_buffer.snapshot())
        self.query_one("#logs", Static).update("Logs\n\n" + "\n".join(state.logs or ["(no logs)"]))
        self.query_one("#keys", Static).update("Keys\n\n" + "\n".join(state.keys or ["(no keys)"]))
        self.query_one("#messages", Static).update("Messages\n\n" + "\n".join(state.messages or ["(no messages)"]))
