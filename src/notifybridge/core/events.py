from __future__ import annotations

import asyncio
import json
from typing import Any


class EventBus:
    """In-process pub/sub contract for UI updates.

    Inputs:
    - Event producers call `publish`.
    - Event consumers iterate over `subscribe`.

    Outputs:
    - Serialized event payloads suitable for SSE forwarding.
    """

    def __init__(self) -> None:
        """Create an empty subscriber registry.

        Inputs:
        - None.

        Outputs:
        - Initializes an event bus with no subscribers.
        """
        self._subscribers: set[asyncio.Queue[str]] = set()

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish one event to all current subscribers.

        Inputs:
        - `event_type`: logical event name.
        - `payload`: JSON-serializable event body.

        Outputs:
        - Queues the serialized event for every active subscriber.
        """
        message = json.dumps({"type": event_type, "payload": payload})
        for queue in list(self._subscribers):
            await queue.put(message)

    async def subscribe(self):
        """Yield events for one subscriber session.

        Inputs:
        - None.

        Outputs:
        - An async generator that yields serialized event strings until cancelled.
        """
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)
