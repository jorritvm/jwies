"""Messages the server sends to a client.

Every message is one of two kinds, and the split is the whole design:

**State.** ``snapshot`` (and, before a game exists, ``lobby_state`` and
``lobby_list``) is the *only* thing a client folds into what it believes about
the table. A fresh per-seat snapshot follows every action that changes
anything, so a client never derives state by replaying events and the two
clients cannot disagree about what an event meant.

**Announcements.** Everything else says what just happened and carries nothing
a client must remember. The three exceptions are ``card_played``,
``trick_completed`` and ``table_cleared``: between a trick being won and being
swept, the table shows four cards that the engine has already collected, so the
snapshot deliberately cannot describe that moment and the clients bridge it.

Every field a player reads is already Dutch: the server renders it from its text
catalog, so neither client owns a translation table for game statements. Clients
only supply Dutch for their own static widget labels.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from jwies_server.protocol.common import (
    CardCode,
    LobbyId,
    ProtocolModel,
    SeatIndex,
    Username,
)
from jwies_server.protocol.errors import ErrorCode
from jwies_server.protocol.snapshot import (
    LobbyState,
    LobbySummary,
    PlayedCardInfo,
    SeatInfo,
    Snapshot,
    TrickCounts,
)

__all__ = ["ChatKind", "ServerMessage"]


class ChatKind(StrEnum):
    PLAYER = "player"  # someone typed it
    SERVER = "server"  # the game master speaks
    SYSTEM = "system"  # joins, leaves, errors


# --- state -------------------------------------------------------------------


class HelloOk(ProtocolModel):
    type: Literal["hello_ok"] = "hello_ok"
    player_id: str
    username: Username
    server_version: str
    protocol_version: int
    resume_token: str
    current_lobby: LobbyId | None = None
    rulesets: tuple[str, ...] = ()
    scorings: tuple[str, ...] = ()


class LobbyListing(ProtocolModel):
    type: Literal["lobby_list"] = "lobby_list"
    lobbies: tuple[LobbySummary, ...] = ()


class LobbyStateMessage(ProtocolModel):
    type: Literal["lobby_state"] = "lobby_state"
    lobby: LobbyState


class SnapshotMessage(ProtocolModel):
    """Everything one player may know, including whose turn it is.

    Built per recipient because it carries that player's hand, and sent after
    every change - not only on request.
    """

    type: Literal["snapshot"] = "snapshot"
    snapshot: Snapshot


# --- the trick on the table --------------------------------------------------


class CardPlayed(ProtocolModel):
    type: Literal["card_played"] = "card_played"
    seat: SeatIndex
    card: CardCode
    position_in_trick: int


class TrickCompleted(ProtocolModel):
    type: Literal["trick_completed"] = "trick_completed"
    winner_seat: SeatIndex
    cards: tuple[PlayedCardInfo, ...]
    trick_counts: TrickCounts
    text: str = ""


class TableCleared(ProtocolModel):
    """Sent after the ruleset's pause, once the trick has been admired."""

    type: Literal["table_cleared"] = "table_cleared"


# --- announcements -----------------------------------------------------------


class Error(ProtocolModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    text: str  # Dutch, safe to show as-is


class Chat(ProtocolModel):
    type: Literal["chat"] = "chat"
    kind: ChatKind
    text: str
    sender: Username | None = None
    private: bool = False


class GameStarted(ProtocolModel):
    type: Literal["game_started"] = "game_started"
    lobby_id: LobbyId
    seats: tuple[SeatInfo, ...]
    your_seat: SeatIndex


class RoundFinished(ProtocolModel):
    """The settlement. ``deltas`` is the one thing no snapshot carries."""

    type: Literal["round_finished"] = "round_finished"
    tricks_made: int
    made: bool
    deltas: dict[Username, str]
    totals: dict[Username, str]
    text: str


class GameFinished(ProtocolModel):
    type: Literal["game_finished"] = "game_finished"
    totals: dict[Username, str]
    text: str


class PlayerJoined(ProtocolModel):
    type: Literal["player_joined"] = "player_joined"
    username: Username
    seat: SeatIndex | None = None


class PlayerLeft(ProtocolModel):
    type: Literal["player_left"] = "player_left"
    username: Username


class PlayerDisconnected(ProtocolModel):
    type: Literal["player_disconnected"] = "player_disconnected"
    username: Username
    seat: SeatIndex | None = None


class PlayerReconnected(ProtocolModel):
    type: Literal["player_reconnected"] = "player_reconnected"
    username: Username
    seat: SeatIndex | None = None


class GamePaused(ProtocolModel):
    type: Literal["game_paused"] = "game_paused"
    missing: tuple[Username, ...]
    text: str


class GameResumed(ProtocolModel):
    type: Literal["game_resumed"] = "game_resumed"
    text: str


class Pong(ProtocolModel):
    type: Literal["pong"] = "pong"


ServerMessage: TypeAlias = Annotated[
    HelloOk
    | Error
    | LobbyListing
    | LobbyStateMessage
    | Chat
    | GameStarted
    | SnapshotMessage
    | CardPlayed
    | TrickCompleted
    | TableCleared
    | RoundFinished
    | GameFinished
    | PlayerJoined
    | PlayerLeft
    | PlayerDisconnected
    | PlayerReconnected
    | GamePaused
    | GameResumed
    | Pong,
    Field(discriminator="type"),
]
