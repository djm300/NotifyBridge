from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import logging
from threading import Lock


@dataclass(slots=True)
class LogEntry:
    """Immutable log snapshot contract.

    Inputs:
    - `level`: rendered log level name.
    - `message`: fully formatted log line.

    Outputs:
    - A value object stored by `LogBuffer` and rendered by the TUI.

    Why the decorator is used:
    - `@dataclass` keeps this record type compact and explicit because it only
      carries structured log data and does not need custom behavior.
    """
    level: str
    message: str


class LogBuffer(logging.Handler):
    """In-memory log sink for UI consumption.

    Why inheritance is used:
    - This inherits from `logging.Handler` so standard Python logging can publish
      into the TUI/log buffer without a custom logging pipeline.
    """

    def __init__(self, max_entries: int = 200) -> None:
        """Create a bounded log buffer.

        Inputs:
        - `max_entries`: maximum number of retained log lines.

        Outputs:
        - Initializes a handler that stores recent formatted logs in memory.
        """
        super().__init__()
        self._entries: deque[LogEntry] = deque(maxlen=max_entries)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """Store one formatted log record.

        Inputs:
        - `record`: a standard `logging.LogRecord`.

        Outputs:
        - Appends one `LogEntry` into the in-memory buffer.
        """
        entry = LogEntry(level=record.levelname, message=self.format(record))
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> list[LogEntry]:
        """Return a stable copy of buffered logs.

        Inputs:
        - None.

        Outputs:
        - A list of `LogEntry` objects ordered by insertion time.
        """
        with self._lock:
            return list(self._entries)


def configure_logging(log_buffer: LogBuffer) -> logging.Logger:
    """Configure the application logger.

    Inputs:
    - `log_buffer`: the in-memory handler used by the TUI and debug views.

    Outputs:
    - Returns the configured `notifybridge` logger with stdout and buffer handlers attached.
    """
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
