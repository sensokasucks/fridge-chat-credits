"""Base class every platform adapter (twitch, kick, youtube, stream_core) extends.

An adapter connects to one chat source, turns each message into a ChatEvent
(core/models.py) and publishes it on the EventBus. main.py creates the adapters
that are enabled in config.yaml, calls start() at boot and stop() on shutdown.
"""

from __future__ import annotations

import abc
import logging

from core.event_bus import EventBus
from core.models import ChatEvent, Platform

log = logging.getLogger("adapters.base")


class BaseAdapter(abc.ABC):
    """Common shape of a chat listener. Subclasses set ``platform``."""

    platform: Platform

    def __init__(self, config: dict, bus: EventBus):
        self.config = config
        self.bus = bus
        self._running = False

    # Begin listening (usually spawns a background task). Must return quickly.
    @abc.abstractmethod
    async def start(self) -> None: ...

    # Stop listening and close any connection. Called once at shutdown.
    @abc.abstractmethod
    async def stop(self) -> None: ...

    # Hand a normalized message to the bus (ChatCredits._on_chat in main.py feeds it to the roster).
    async def _emit(self, event: ChatEvent) -> None:
        await self.bus.publish_chat(event)
