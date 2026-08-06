"""Identity and reconnection.

There is no login system: a player supplies a username, and that username is
the key used to bind them back to their seat when they return. A resume token
is issued on first contact and makes the normal reconnect unambiguous.
"""

from __future__ import annotations

import re
import secrets
import time
import unicodedata
from dataclasses import dataclass, field
from enum import Enum, auto

from jwies_server.agents import PlayerAgent

__all__ = [
    "USERNAME_CHARACTERS",
    "USERNAME_MAX_LENGTH",
    "USERNAME_MIN_LENGTH",
    "HelloOutcome",
    "Session",
    "SessionRegistry",
    "normalise_username",
]

USERNAME_MIN_LENGTH = 2
USERNAME_MAX_LENGTH = 20

# A name is what somebody calls themselves, so any script writes one: `\w` is
# unicode here, which covers Jos**é**, Ж, and 山 as readily as J. Beyond that
# only the punctuation that turns up in real names.
#
# What stays out is not a matter of taste. `<`, `>`, `&` and the quotes would
# have to be escaped correctly by every renderer that ever shows a name - the
# web client does escape them today, but a name that can never contain them is
# one fewer thing that has to keep being true. Control characters go for the
# same reason.
USERNAME_CHARACTERS = re.compile(r"^[\w .'-]+$")


def normalise_username(username: str) -> str:
    """The canonical form of a name: NFC, without surrounding whitespace.

    Composing matters because ``é`` has two spellings - one character, or ``e``
    plus a combining accent - and a player who types their name on a Mac would
    otherwise be a different person from the same player on Windows, with a
    different seat to prove it. Everything downstream (validating, keying,
    displaying) works on this form, so the two spellings are one player.
    """
    return unicodedata.normalize("NFC", username).strip()


class HelloOutcome(Enum):
    """How a ``hello`` was resolved."""

    NEW = auto()
    RESUMED = auto()  # known username, matching token
    REBOUND = auto()  # known username, no/wrong token, old connection dead
    TAKEN = auto()  # known username, old connection still alive -> refuse


@dataclass
class Session:
    """One player's identity, independent of any particular connection."""

    # The username *is* the identity: sessions are keyed by it case-insensitively
    # and reconnect binds on it, so there is no separate player id to keep.
    username: str
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
        """The one place the rules for a name live.

        Deliberately not expressed as a type on ``protocol.Hello``: a name that
        breaks a rule has to reach this function to be told *which* rule, and a
        constrained field would have rejected the envelope one step earlier with
        "onbegrijpelijk bericht" instead.
        """
        name = normalise_username(username)
        return (
            USERNAME_MIN_LENGTH <= len(name) <= USERNAME_MAX_LENGTH
            and bool(USERNAME_CHARACTERS.match(name))
            # Punctuation alone is not a name, and "..." next to "…" at the same
            # table helps nobody.
            and any(character.isalnum() for character in name)
        )

    @staticmethod
    def _key(username: str) -> str:
        # Usernames are unique case-insensitively, so "Jan" and "jan" are the
        # same player coming back rather than two people fighting over a seat.
        return normalise_username(username).casefold()

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
        username = normalise_username(username)
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
