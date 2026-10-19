"""Optional ingest from Fridge Stream Core's existing WebSocket.

Use this instead of a second Kick connection when Core is already running.

Connects to Core's /ws (``ingest.stream_core.ws_url``, default port 3850) and
re-emits its "chat" and "chat_history" messages as ChatEvents with their
original platform. Expected chat payload: {platform, user: {username,
display_name, id, is_mod, is_vip, is_subscriber, badges, color}, message,
message_id}. Do not enable together with kick.enabled (double Kick messages).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed

from adapters.base import BaseAdapter
from core.models import ChatEvent, ChatUser, Platform

log = logging.getLogger("adapters.stream_core")

# Core platform names we accept; anything else is ignored.
_PLATFORM = {
    "kick": Platform.KICK,
    "twitch": Platform.TWITCH,
    "youtube": Platform.YOUTUBE,
}


class StreamCoreIngest(BaseAdapter):
    """Reads chat from a running Stream Core instead of from the platforms directly."""

    platform = Platform.MANUAL  # events keep their original platform

    def __init__(self, config: dict, bus):
        super().__init__(config, bus)
        cfg = (config.get("ingest") or {}).get("stream_core") or {}
        self.ws_url = (cfg.get("ws_url") or "ws://127.0.0.1:3850/ws").strip()
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._running = True
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="core-ingest")
        log.info("Stream Core ingest → %s", self.ws_url)

    async def stop(self) -> None:
        self._running = False
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        backoff = 3.0
        while self._running:
            try:
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:
                    log.info("Connected to Stream Core")
                    backoff = 3.0
                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle(raw)
            except ConnectionClosed:
                log.warning("Stream Core WS closed — retry in %.1fs", backoff)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("Stream Core ingest error: %s — retry in %.1fs", e, backoff)
            if not self._running:
                break
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                break
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 1.5, 20.0)

    async def _handle(self, raw: str | bytes) -> None:
        """Dispatch one Core WS message; other message types are ignored."""
        try:
            msg = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8", "ignore"))
        except json.JSONDecodeError:
            return
        kind = msg.get("type")
        if kind == "chat":
            await self._from_payload(msg.get("data") or {})
        elif kind == "chat_history":
            # A batch of earlier chat messages from Core; each is counted like a live one.
            for item in msg.get("data") or []:
                await self._from_payload(item)

    async def _from_payload(self, data: dict) -> None:
        if not data:
            return
        plat = _PLATFORM.get((data.get("platform") or "").lower())
        user_raw = data.get("user") or {}
        name = user_raw.get("username") or ""
        text = data.get("message") or ""
        if not plat or not name or not text:
            return
        user = ChatUser(
            platform=plat,
            id=str(user_raw.get("id") or name),
            username=name,
            display_name=user_raw.get("display_name") or name,
            is_mod=bool(user_raw.get("is_mod")),
            is_vip=bool(user_raw.get("is_vip")),
            is_subscriber=bool(user_raw.get("is_subscriber")),
            badges=list(user_raw.get("badges") or []),
            color=user_raw.get("color"),
        )
        await self._emit(ChatEvent(
            platform=plat,
            user=user,
            message=text,
            message_id=str(data.get("message_id") or ""),
        ))
