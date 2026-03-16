from __future__ import annotations

from dataclasses import dataclass

from notifybridge.logging_utils import LogEntry
from notifybridge.storage.repository import Repository


@dataclass(slots=True)
class TUIState:
    logs: list[str]
    keys: list[str]
    messages: list[str]


def build_tui_state(repository: Repository, logs: list[LogEntry]) -> TUIState:
    key_lines = [
        f"{item.api_key} | total={item.total_count} new={item.new_count} read={item.read_count}"
        for item in repository.list_key_summaries()
    ]
    if repository.get_syslog_mode() == "permissive":
        summary = repository.unassigned_summary()
        key_lines.append(
            f"unassigned-syslog | total={summary.total_count} new={summary.new_count} read={summary.read_count}"
        )
    messages = [
        f"[{item.source_type}] {item.api_key or 'unassigned'} | {item.title}"
        for item in repository.list_notifications()[:25]
    ]
    return TUIState(
        logs=[entry.message for entry in logs[-25:]],
        keys=key_lines,
        messages=messages,
    )
