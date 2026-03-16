from __future__ import annotations

from dataclasses import dataclass
import logging

from notifybridge.config import Settings
from notifybridge.core.events import EventBus
from notifybridge.core.ingestion import IngestionService
from notifybridge.logging_utils import LogBuffer, configure_logging
from notifybridge.storage.repository import Repository


@dataclass(slots=True)
class Runtime:
    """Application runtime contract bundling shared services.

    Why the decorator is used:
    - `@dataclass` keeps the runtime graph explicit and easy to pass around
      without writing manual initializer boilerplate.
    """
    settings: Settings
    repository: Repository
    event_bus: EventBus
    ingestion: IngestionService
    log_buffer: LogBuffer
    logger: logging.Logger


def build_runtime(settings: Settings) -> Runtime:
    """Construct the application runtime graph.

    Inputs:
    - `settings`: loaded runtime configuration.

    Outputs:
    - `Runtime` containing config, storage, logging, event bus, and ingestion service.
    """
    log_buffer = LogBuffer()
    logger = configure_logging(log_buffer)
    repository = Repository(settings.sqlite_path)
    repository.set_syslog_mode(settings.permissive_syslog)
    event_bus = EventBus()
    ingestion = IngestionService(repository, event_bus, settings.email_domain)
    return Runtime(
        settings=settings,
        repository=repository,
        event_bus=event_bus,
        ingestion=ingestion,
        log_buffer=log_buffer,
        logger=logger,
    )
