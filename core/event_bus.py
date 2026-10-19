"""In-process async bus. Adapters publish ChatEvents; main.py's handler listens.

There is only one event kind (chat). Handlers run one after another in the
order they were registered; one failing handler is logged and does not stop
the others.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, List

from .models import ChatEvent

log = logging.getLogger("core.event_bus")

# A handler is an async function that takes one ChatEvent.
ChatHandler = Callable[[ChatEvent], Awaitable[None]]


class EventBus:
    def __init__(self):
        self._chat_handlers: List[ChatHandler] = []

    # Register an async handler for every chat message (main.py: ChatCredits.start).
    def on_chat(self, handler: ChatHandler) -> None:
        self._chat_handlers.append(handler)

    # Await each handler in turn. Called by BaseAdapter._emit and the /api/seed route.
    async def publish_chat(self, event: ChatEvent) -> None:
        for handler in self._chat_handlers:
            try:
                await handler(event)
            except Exception:
                log.exception("chat handler failed")
