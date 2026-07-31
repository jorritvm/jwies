"""Messages the server sends to a client.

Every field that a player reads is already Dutch: the server renders it from
its text catalog, so neither client has to own a translation table for game
statements. Clients only supply Dutch for their own static widget labels.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from jwies_protocol.common import (
    CardCode,
    LobbyId,
    PhaseCode,
    ProtocolModel,
    SeatIndex,
    SuitCode,
    Username,
)
from jwies_protocol.errors import ErrorCode
from jwies_protocol.snapshot import (
    BidInfo,
    ContractInfo,
    LobbyState,
    LobbySummary,
    PlayedCardInfo,
    Prompt,
    SeatInfo,
    Snapshot,
    TrickCounts,
)

__all__ = ["ChatKind", "ServerMessage"]


class ChatKind(StrEnum):
    PLAYER = "player"  # someone typed it
    SERVER = "server"  # the game master speaks
    SYSTEM = "system"  # joins, leaves, errors


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


class Error(ProtocolModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    text: str  # Dutch, safe to show as-is


class LobbyListing(ProtocolModel):
    type: Literal["lobby_list"] = "lobby_list"
    lobbies: tuple[LobbySummary, ...] = ()


class LobbyStateMessage(ProtocolModel):
    type: Literal["lobby_state"] = "lobby_state"
    lobby: LobbyState


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


class SnapshotMessage(ProtocolModel):
    type: Literal["snapshot"] = "snapshot"
    snapshot: Snapshot


class PromptMessage(ProtocolModel):
    type: Literal["prompt"] = "prompt"
    prompt: Prompt


class PromptCleared(ProtocolModel):
    type: Literal["prompt_cleared"] = "prompt_cleared"


class RoundStarted(ProtocolModel):
    type: Literal["round_started"] = "round_started"
    round_number: int
    dealer_seat: SeatIndex
    multiplier: str = "1"


class HandDealt(ProtocolModel):
    """Private: only ever sent to the owner of the hand."""

    type: Literal["hand_dealt"] = "hand_dealt"
    cards: tuple[CardCode, ...]


class TrumpTurned(ProtocolModel):
    type: Literal["trump_turned"] = "trump_turned"
    dealer_seat: SeatIndex
    card: CardCode


class TrumpHidden(ProtocolModel):
    type: Literal["trump_hidden"] = "trump_hidden"


class BidPlaced(ProtocolModel):
    type: Literal["bid_placed"] = "bid_placed"
    seat: SeatIndex
    bid: BidInfo
    forced: bool = False
    announcement: str = ""  # Dutch, e.g. "Jan: IK GA HARTEN VRAGEN"


class Redeal(ProtocolModel):
    type: Literal["redeal"] = "redeal"
    reason: str
    text: str


class ContractEstablished(ProtocolModel):
    type: Literal["contract_established"] = "contract_established"
    contract: ContractInfo
    text: str


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


class RoundFinished(ProtocolModel):
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


class PhaseChanged(ProtocolModel):
    type: Literal["phase_changed"] = "phase_changed"
    phase: PhaseCode


class TrumpDecided(ProtocolModel):
    type: Literal["trump_decided"] = "trump_decided"
    trump: SuitCode | None = None


ServerMessage: TypeAlias = Annotated[
    HelloOk
    | Error
    | LobbyListing
    | LobbyStateMessage
    | Chat
    | GameStarted
    | SnapshotMessage
    | PromptMessage
    | PromptCleared
    | RoundStarted
    | HandDealt
    | TrumpTurned
    | TrumpHidden
    | TrumpDecided
    | BidPlaced
    | Redeal
    | ContractEstablished
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
    | PhaseChanged
    | Pong,
    Field(discriminator="type"),
]
