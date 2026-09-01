#!/usr/bin/env python3
"""
Fridge Chat Credits — standalone unique-chatter credits roll.

Adapters (Twitch / Kick / YouTube / Stream Core ingest) feed an in-process
bus. The roster keeps one row per (platform, username). An HTML overlay
renders a configurable end-credits marquee for XSplit / OBS.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.kick import KickAdapter
from adapters.stream_core import StreamCoreIngest
from adapters.twitch import TwitchAdapter
from adapters.youtube import YouTubeAdapter
from api.server import AppState, create_app, load_theme, roster_payload
from core.cast import CastBoard
from core.config import load_config
from core.event_bus import EventBus
from core.models import ChatEvent, ChatUser, Platform
from core.roster import Roster

log = logging.getLogger("main")


class ChatCredits:
    def __init__(self, config: dict):
        self.config = config
        self.bus = EventBus()
        ignore = list(config.get("roster", {}).get("ignore_usernames") or [])
        if config.get("roster", {}).get("ignore_own_channel", True):
            kick_slug = (config.get("kick") or {}).get("channel_slug") or ""
            tw = (config.get("twitch") or {}).get("channel") or ""
            if kick_slug and not kick_slug.startswith("YOUR_"):
                ignore.append(kick_slug)
            if tw and not tw.startswith("your_"):
                ignore.append(tw)
        session = Path(config.get("app", {}).get("session_file") or "data/session.json")
        if not session.is_absolute():
            session = ROOT / session
        self.roster = Roster(
            path=session,
            ignore=ignore,
            min_len=int(config.get("roster", {}).get("min_message_length") or 1),
        )
        self.roster.load()
        self.state = AppState()
        self.state.config = config
        self.state.roster = self.roster
        self.state.root = ROOT
        self.state.bus = self.bus
        self.cast = CastBoard(ROOT, allow_alert_groups=False)
        self.cast.set_style((config.get("credits") or {}).get("style_id") or "names")
        self.state.cast = self.cast
        load_theme(self.state)
        if os.environ.get("CREDITS_DEMO") == "1":
            self.cast.set_style("movie")
            self.state.theme["style_id"] = "movie"
            self.state.theme["style"] = "movie"
            self.state.theme["letterbox"] = True
            self.state.theme["grain"] = True
            self.state.theme["vignette"] = True
            self.state.theme["duration_sec"] = 55
            self.state.theme["mode"] = "loop"
            if (self.state.theme.get("background") or "transparent") == "transparent":
                self.state.theme["background"] = "#000"
        self.state.theme["style_id"] = self.cast.style_id
        self.state.theme["style"] = self.cast.get_style().get("style") or "names"
        self.state.play["mode"] = self.state.theme.get("mode") or "loop"
        self.state.apply_config = self.apply_runtime_config
        self.adapters: dict = {}
        self.state.adapters = self.adapters
        self._save_task: asyncio.Task | None = None
        self._pending_broadcast = False

    async def start(self) -> None:
        self.bus.on_chat(self._on_chat)
        self.roster.on_change(self._mark_broadcast)

        twitch_cfg = self.config.get("twitch") or {}
        if twitch_cfg.get("enabled"):
            tw = TwitchAdapter(self.config, self.bus)
            await tw.start()
            self.adapters["twitch"] = tw

        kick_cfg = self.config.get("kick") or {}
        if kick_cfg.get("enabled"):
            kick = KickAdapter(self.config, self.bus)
            await kick.start()
            self.adapters["kick"] = kick

        yt_cfg = self.config.get("youtube") or {}
        if yt_cfg.get("enabled"):
            yt = YouTubeAdapter(self.config, self.bus)
            await yt.start()
            self.adapters["youtube"] = yt

        ingest_cfg = (self.config.get("ingest") or {}).get("stream_core") or {}
        if ingest_cfg.get("enabled"):
            if kick_cfg.get("enabled"):
                log.warning(
                    "Both Kick adapter and Stream Core ingest are on — "
                    "you will see duplicate Kick names. Disable one."
                )
            ingest = StreamCoreIngest(self.config, self.bus)
            await ingest.start()
            self.adapters["stream_core"] = ingest

        save_every = float(self.config.get("app", {}).get("save_every_sec") or 10)
        self._save_task = asyncio.create_task(self._persist_loop(save_every), name="persist")
        if os.environ.get("CREDITS_DEMO") == "1" and not self.roster.chatters:
            await self._seed_demo()
        log.info(
            "Chat Credits ready — %s unique so far, adapters=%s",
            len(self.roster.chatters),
            list(self.adapters.keys()) or "(none configured)",
        )

    async def stop(self) -> None:
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        for adapter in self.adapters.values():
            await adapter.stop()
        self.roster.save()
        log.info("Chat Credits stopped")

    def apply_runtime_config(self, config: dict) -> None:
        """Hot-apply ignore list / theme. Adapter toggles still need a restart."""
        self.config = config
        self.state.config = config
        roster_cfg = config.get("roster") or {}
        ignore = list(roster_cfg.get("ignore_usernames") or [])
        if roster_cfg.get("ignore_own_channel", True):
            kick_slug = (config.get("kick") or {}).get("channel_slug") or ""
            tw = (config.get("twitch") or {}).get("channel") or ""
            if kick_slug and not str(kick_slug).startswith("YOUR_"):
                ignore.append(kick_slug)
            if tw and not str(tw).startswith("your_"):
                ignore.append(tw)
        self.roster.ignore = {n.lower().strip() for n in ignore if n}
        self.roster.min_len = max(0, int(roster_cfg.get("min_message_length") or 1))
        if isinstance(config.get("credits"), dict):
            self.state.theme.update(config["credits"])

    def _mark_broadcast(self) -> None:
        self._pending_broadcast = True

    async def _on_chat(self, event: ChatEvent) -> None:
        self.roster.ingest(event)

    async def _seed_demo(self) -> None:
        """Preview-only names so the roll has something to crawl."""
        samples = [
            (Platform.TWITCH, "AriaVox", True, True, 12),
            (Platform.TWITCH, "pixelranch", False, True, 9),
            (Platform.KICK, "NeonHarbor", False, True, 7),
            (Platform.KICK, "mod_maple", True, True, 5),
            (Platform.YOUTUBE, "Lo-Fi Lynx", False, False, 4),
            (Platform.TWITCH, "copperkettle", False, True, 3),
            (Platform.KICK, "questinggnat", False, False, 2),
            (Platform.YOUTUBE, "StudioMoth", False, True, 2),
            (Platform.TWITCH, "emberwalk", False, False, 1),
            (Platform.KICK, "saltandbit", False, False, 1),
            (Platform.TWITCH, "nightorchard", False, True, 1),
            (Platform.YOUTUBE, "viscounttea", False, False, 1),
            (Platform.KICK, "bramblecast", False, False, 1),
            (Platform.TWITCH, "softcheckpoint", False, False, 1),
            (Platform.MANUAL, "the_crew", False, False, 1),
            (Platform.TWITCH, "riverglass", False, False, 1),
            (Platform.KICK, "hexlane", False, False, 1),
            (Platform.YOUTUBE, "paperlantern", False, False, 1),
            (Platform.TWITCH, "duskparcel", False, False, 1),
            (Platform.KICK, "wildstatic", False, False, 1),
            (Platform.TWITCH, "lowpolyfarm", False, False, 1),
            (Platform.KICK, "coastalping", False, False, 1),
            (Platform.YOUTUBE, "amberthread", False, False, 1),
            (Platform.TWITCH, "silentcart", False, False, 1),
            (Platform.KICK, "fogandfiber", False, False, 1),
            (Platform.TWITCH, "rookandrelay", False, False, 1),
            (Platform.YOUTUBE, "tinwhistle", False, False, 1),
            (Platform.KICK, "copperline", False, False, 1),
            (Platform.TWITCH, "moonwell", False, False, 1),
            (Platform.KICK, "atlascrumb", False, False, 1),
            (Platform.YOUTUBE, "firstlight", False, False, 1),
            (Platform.TWITCH, "peatandpine", False, False, 1),
            (Platform.KICK, "silverlatch", False, False, 1),
            (Platform.TWITCH, "harborfinch", False, False, 1),
            (Platform.YOUTUBE, "quiltedbyte", False, False, 1),
            (Platform.KICK, "northkiln", False, False, 1),
        ]
        for plat, name, is_mod, is_sub, n in samples:
            name = name.strip()
            user = ChatUser(
                platform=plat,
                id=name,
                username=name,
                display_name=name,
                is_mod=is_mod,
                is_subscriber=is_sub,
            )
            for i in range(n):
                await self.bus.publish_chat(ChatEvent(
                    platform=plat,
                    user=user,
                    message="(demo)",
                ))
        try:
            self.cast.pin("twitch", "ariavox", "Director", set_by="demo")
            self.cast.pin("kick", "mod_maple", "Showrunner", set_by="demo")
        except Exception:
            pass
        log.info("Seeded %s demo chatters for preview", len(samples))

    async def _persist_loop(self, every: float) -> None:
        while True:
            await asyncio.sleep(every)
            try:
                self.roster.save_if_dirty()
            except Exception:
                log.exception("session save failed")
            if self._pending_broadcast and self.state.ws:
                self._pending_broadcast = False
                if not self.state.play.get("freeze"):
                    try:
                        await self.state.ws.broadcast(
                            {"type": "roster", "data": roster_payload(self.state)}
                        )
                    except Exception:
                        log.exception("roster broadcast failed")


async def _run() -> None:
    config = load_config(ROOT)
    level = str(config.get("app", {}).get("log_level") or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    app_core = ChatCredits(config)
    await app_core.start()

    host = os.environ.get("CREDITS_HOST") or config.get("app", {}).get("host") or "127.0.0.1"
    port = int(os.environ.get("CREDITS_PORT") or config.get("app", {}).get("port") or 3854)
    fastapi_app = create_app(app_core.state)

    uv_config = uvicorn.Config(
        fastapi_app,
        host=host,
        port=port,
        log_level=level.lower(),
        lifespan="on",
    )
    server = uvicorn.Server(uv_config)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _ask_stop(*_):
        stop.set()
        server.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _ask_stop)
        except NotImplementedError:
            pass

    log.info("HTTP on http://%s:%s  overlay /overlay/credits.html", host, port)
    try:
        await server.serve()
    finally:
        await app_core.stop()


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
