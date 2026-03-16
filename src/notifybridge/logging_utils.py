from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import logging
from threading import Lock


@dataclass(slots=True)
class LogEntry:
    level: str
    message: str


class LogBuffer(logging.Handler):
    def __init__(self, max_entries: int = 200) -> None:
        super().__init__()
        self._entries: deque[LogEntry] = deque(maxlen=max_entries)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = LogEntry(level=record.levelname, message=self.format(record))
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> list[LogEntry]:
        with self._lock:
            return list(self._entries)


def configure_logging(log_buffer: LogBuffer) -> logging.Logger:
    logger = logging.getLogger("notifybridge")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log_buffer.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(log_buffer)
    return logger
