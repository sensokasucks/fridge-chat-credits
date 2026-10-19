"""Normalized chat types shared by every adapter.

ChatUser / ChatEvent are what adapters build from a platform message.
Chatter is one row in the roster (core/roster.py); its to_dict() shape is
what data/session.json stores and what the overlay receives as ``chatters``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional
import time


# The string values are what JSON, the overlay and "platform:username" keys use.
class Platform(str, Enum):
    KICK = "kick"
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    MANUAL = "manual"


@dataclass
class ChatUser:
    """Who sent a message, as reported by the platform."""

    platform: Platform
    id: str
    username: str
    display_name: str = ""
    is_mod: bool = False
    is_vip: bool = False
    is_subscriber: bool = False
    is_paid: bool = False
    badges: list[str] = field(default_factory=list)
    color: Optional[str] = None

    def __post_init__(self):
        # The display name keeps its case; username is lowercased because it is
        # part of the roster identity (platform, username).
        if not self.display_name:
            self.display_name = self.username
        self.username = (self.username or "").lower().strip()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["platform"] = self.platform.value
        return d


@dataclass
class ChatEvent:
    """One chat message. ``timestamp`` is Unix seconds; ``raw`` keeps the platform payload."""

    platform: Platform
    user: ChatUser
    message: str
    timestamp: float = field(default_factory=time.time)
    message_id: Optional[str] = None
    is_paid: bool = False
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["platform"] = self.platform.value
        d["user"] = self.user.to_dict()
        return d


@dataclass
class Chatter:
    """One unique person on one platform for this session."""

    platform: str
    username: str
    display_name: str
    first_seen: float
    last_seen: float
    messages: int = 1
    color: Optional[str] = None
    is_mod: bool = False
    is_vip: bool = False
    is_subscriber: bool = False
    is_paid: bool = False

    # Roster dict key, e.g. "twitch:somebody". Matches Roster.ingest().
    @property
    def key(self) -> str:
        return f"{self.platform}:{self.username}"

    def to_dict(self) -> dict:
        return asdict(self)

    # Rebuild a Chatter from session.json; missing fields get safe defaults.
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chatter":
        return cls(
            platform=str(data.get("platform") or ""),
            username=str(data.get("username") or ""),
            display_name=str(data.get("display_name") or data.get("username") or ""),
            first_seen=float(data.get("first_seen") or 0),
            last_seen=float(data.get("last_seen") or 0),
            messages=int(data.get("messages") or 1),
            color=data.get("color"),
            is_mod=bool(data.get("is_mod")),
            is_vip=bool(data.get("is_vip")),
            is_subscriber=bool(data.get("is_subscriber")),
            is_paid=bool(data.get("is_paid")),
        )
