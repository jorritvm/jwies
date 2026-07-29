"""Identity and reconnection.

There is no login system: a player supplies a username, and that username is
the key used to bind them back to their seat when they return. A resume token
is issued on first contact and makes the normal reconnect unambiguous.
"""

from __future__ import annotations

import re
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto

from jwies_server.agents import PlayerAgent

__all__ = ["USERNAME_PATTERN", "HelloOutcome", "Session", "SessionRegistry"]

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\- ]{2,20}$")


class HelloOutcome(Enum):
    """How a ``hello`` was resolved."""

    NEW = auto()
    RESUMED = auto()  # known username, matching token
    REBOUND = auto()  # known username, no/wrong token, old connection dead
    TAKEN = auto()  # known username, old connection still alive -> refuse


@dataclass
class Session:
    """One player's identity, independent of any particular connection."""

    username: str
    player_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resume_token: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    lobby_id: str | None = None
    seat: int | None = None
    agent: PlayerAgent | None = None
    last_seen: float = field(default_factory=time.monotonic)

    @property
    def connected(self) -> bool:
        return self.agent is not None

    def touch(self) -> None:
        self.last_seen = time.monotonic()

    def disconnect(self) -> None:
        self.agent = None
        self.touch()


class SessionRegistry:
    """All known players, alive or merely remembered."""

    def __init__(self) -> None:
        self._by_key: dict[str, Session] = {}

    @staticmethod
    def is_valid_username(username: str) -> bool:
        return bool(USERNAME_PATTERN.match(username))

    @staticmethod
    def _key(username: str) -> str:
        # Usernames are unique case-insensitively, so "Jan" and "jan" are the
        # same player coming back rather than two people fighting over a seat.
        return username.strip().casefold()

    def get(self, username: str) -> Session | None:
        return self._by_key.get(self._key(username))

    def all(self) -> list[Session]:
        return list(self._by_key.values())

    def resolve_hello(
        self, username: str, resume_token: str | None
    ) -> tuple[Session, HelloOutcome]:
        """Find or create the session for an arriving connection.

        The four cases are deliberate:

        1. unknown username           -> new session, fresh token
        2. known + matching token     -> resume (the normal reconnect)
        3. known, bad token, old dead -> rebind anyway; username is the key
        4. known, bad token, old live -> refuse, so two clients cannot fight
        """
        username = username.strip()
        existing = self.get(username)

        if existing is None:
            session = Session(username=username)
            self._by_key[self._key(username)] = session
            return session, HelloOutcome.NEW

        if resume_token and secrets.compare_digest(resume_token, existing.resume_token):
            existing.touch()
            return existing, HelloOutcome.RESUMED

        if existing.connected:
            return existing, HelloOutcome.TAKEN

        existing.touch()
        return existing, HelloOutcome.REBOUND

    def forget(self, username: str) -> None:
        self._by_key.pop(self._key(username), None)

    def stale(self, older_than_seconds: float) -> list[Session]:
        """Disconnected sessions untouched for longer than the given time."""
        cutoff = time.monotonic() - older_than_seconds
        return [
            session
            for session in self._by_key.values()
            if not session.connected and session.last_seen < cutoff
        ]
