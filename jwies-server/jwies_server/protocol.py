"""The wire protocol between the jwies server and its clients.

Pydantic models describing every message that crosses the socket. The server
validates everything on the way in and constructs everything on the way out from
these types, so an unknown message is a validation error rather than a silently
ignored dict.

**Neither client imports this.** Both the PyQt and the browser client hand-build
JSON and read raw dicts back, which is what keeps the browser buildless and the
desktop client free of any dependency on the server. So this is the server's own
contract, not a library two parties share - which means the enum *values* and
the field *names* are load-bearing, and the class names are not.
``tests/e2e/test_client_protocol_drift.py`` is what stops a client falling
behind, and ``docs/architecture/protocol.md`` is the human-readable version.

Two ideas shape everything below.

**State versus announcements.** ``snapshot`` - and, before a game exists,
``lobby_state`` and ``lobby_list`` - is the *only* thing a client folds into what
it believes about the table. A fresh per-seat snapshot follows every action that
changes anything, so no client derives state by replaying events and the two
clients cannot disagree about what an event meant. Everything else says what just
happened and carries nothing a client must remember. The exceptions are
``card_played``, ``trick_completed`` and ``table_cleared``: between a trick being
won and being swept, the table shows four cards the engine has already collected,
and no snapshot can describe that moment.

**The snapshot is built per recipient**, never broadcast, because it carries that
player's hand and the legal moves for their turn.

Every field a player reads is already Dutch: the server renders it, so neither
client owns a translation table for game statements.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from jwies_core.bidding import Bid, BidType
from jwies_core.cards import Card, Suit
from jwies_core.contracts import ContractKey
from jwies_core.engine import Phase, PromptKind
from jwies_core.events import Action, Cut, Shuffle
from jwies_core.events import Fold as FoldAction
from jwies_core.events import PlaceBid as PlaceBidAction
from jwies_core.events import PlayCard as PlayCardAction

# The `# --- section ---` headers below are the table of contents; this list is
# just the export surface, so it is kept in the order the linter wants.
__all__ = [
    "PROTOCOL_VERSION",
    "AnswerCut",
    "AnswerShuffle",
    "BidInfo",
    "BidRecord",
    "BidTypeCode",
    "CardCode",
    "CardPlayed",
    "Chat",
    "ChatKind",
    "ChatSend",
    "ClientEnvelope",
    "ClientMessage",
    "ContractInfo",
    "ContractKeyCode",
    "Error",
    "ErrorCode",
    "FoldVote",
    "GameAction",
    "GamePaused",
    "GameResumed",
    "GameStarted",
    "Hello",
    "HelloOk",
    "LobbyCreate",
    "LobbyDelete",
    "LobbyId",
    "LobbyJoin",
    "LobbyLeave",
    "LobbyList",
    "LobbyListing",
    "LobbyMember",
    "LobbyState",
    "LobbyStateMessage",
    "LobbyStatusCode",
    "LobbySummary",
    "PhaseCode",
    "PlaceBid",
    "PlayCard",
    "PlayedCardInfo",
    "PlayerDisconnected",
    "PlayerJoined",
    "PlayerLeft",
    "PlayerReconnected",
    "Prompt",
    "PromptKindCode",
    "ProtocolModel",
    "RequestSnapshot",
    "RoundFinished",
    "SeatIndex",
    "SeatInfo",
    "ServerEnvelope",
    "ServerMessage",
    "Snapshot",
    "SnapshotMessage",
    "SuitCode",
    "TableCleared",
    "TrickCompleted",
    "TrickCounts",
    "Username",
]

PROTOCOL_VERSION: Final = 2


# --- primitives ---------------------------------------------------------------

CardCode: TypeAlias = Annotated[str, Field(pattern=r"^(?:[2-9]|10|[JQKA])[CDHS]$")]
SeatIndex: TypeAlias = Annotated[int, Field(ge=0, le=3)]
LobbyId: TypeAlias = Annotated[str, Field(min_length=1, max_length=64)]
# Only a length bound, on purpose. Which characters make a name is decided in
# exactly one place, ``SessionRegistry.is_valid_username``, and repeating that
# rule here as a pattern would put two regex engines - pydantic's and Python's -
# in charge of the same question. The day they disagreed, the server would go
# back to answering "onbegrijpelijk bericht" for a name it can describe
# perfectly well. Every name that reaches a server message has already passed
# the door.
Username: TypeAlias = Annotated[str, Field(min_length=1, max_length=64)]
# The ``*Code`` names are aliases of the engine's own enums, not copies: the
# alias is the guarantee that they can't drift apart. The names are kept
# because they read better at the wire boundary.
SuitCode = Suit
BidTypeCode = BidType
ContractKeyCode = ContractKey
PhaseCode = Phase
PromptKindCode = PromptKind


class ProtocolModel(BaseModel):
    """Base for every wire model: strict, immutable, no silent extra fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class LobbyStatusCode(StrEnum):
    """Purely a server concept - the engine has no idea lobbies exist."""

    WAITING = "waiting"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    BROKEN = "broken"


class ErrorCode(StrEnum):
    """Clients switch on the code; the accompanying ``text`` is already Dutch."""

    PROTOCOL_VERSION = "protocol_version"
    USERNAME_TAKEN = "username_taken"
    USERNAME_INVALID = "username_invalid"
    NOT_IN_LOBBY = "not_in_lobby"
    LOBBY_FULL = "lobby_full"
    LOBBY_NOT_FOUND = "lobby_not_found"
    LOBBY_EXISTS = "lobby_exists"
    NOT_HOST = "not_host"
    # Acting out of turn arrives as ILLEGAL_MOVE: the engine raises one
    # IllegalAction for every refused move, and its Dutch text already says
    # "het is niet jouw beurt".
    ILLEGAL_MOVE = "illegal_move"
    GAME_PAUSED = "game_paused"
    GAME_NOT_RUNNING = "game_not_running"
    UNKNOWN_RULESET = "unknown_ruleset"
    UNKNOWN_SCORING = "unknown_scoring"
    BAD_MESSAGE = "bad_message"
    INTERNAL = "internal"


class ChatKind(StrEnum):
    PLAYER = "player"  # someone typed it
    SERVER = "server"  # the game master speaks
    SYSTEM = "system"  # joins, leaves, errors


# --- structures ---------------------------------------------------------------


class BidInfo(ProtocolModel):
    """A bid as it travels on the wire."""

    type: BidTypeCode
    tricks: int | None = None
    suit: SuitCode | None = None


class BidRecord(ProtocolModel):
    seat: SeatIndex
    bid: BidInfo
    announcement: str = ""  # Dutch, rendered server-side


class PlayedCardInfo(ProtocolModel):
    seat: SeatIndex
    card: CardCode


class ContractInfo(ProtocolModel):
    key: ContractKeyCode
    name: str  # Dutch display name
    tricks_required: int
    declarers: tuple[SeatIndex, ...]
    trump: SuitCode | None = None


class TrickCounts(ProtocolModel):
    declarers: int = 0
    defenders: int = 0


class SeatInfo(ProtocolModel):
    seat: SeatIndex
    username: Username | None = None
    connected: bool = False
    is_dealer: bool = False


class Prompt(ProtocolModel):
    """What the server is waiting for from *you*, with the legal options.

    A client never has to derive follow-suit or the bidding ladder itself.
    """

    kind: PromptKindCode
    bid_options: tuple[BidInfo, ...] = ()
    legal_cards: tuple[CardCode, ...] = ()
    cut_minimum: int = 0
    cut_maximum: int = 0


class LobbyMember(ProtocolModel):
    username: Username
    seat: SeatIndex | None = None
    connected: bool = True
    is_host: bool = False


class LobbyState(ProtocolModel):
    id: str
    name: str
    host: Username | None = None
    ruleset: str
    scoring: str
    status: LobbyStatusCode
    members: tuple[LobbyMember, ...] = ()


class LobbySummary(ProtocolModel):
    """One row in the lobby list."""

    id: str
    name: str
    ruleset: str
    scoring: str
    status: LobbyStatusCode
    players: int
    seats_free: int


class Snapshot(ProtocolModel):
    """Everything one player may know about the table right now."""

    phase: PhaseCode
    round_number: int = 0
    multiplier: str = "1"
    your_seat: SeatIndex | None = None
    dealer_seat: SeatIndex | None = None
    seats: tuple[SeatInfo, ...] = ()
    your_hand: tuple[CardCode, ...] = ()
    # Only populated for misere ouverte, where hands lie face up.
    open_hands: dict[SeatIndex, tuple[CardCode, ...]] = {}
    turned_trump: CardCode | None = None
    trump: SuitCode | None = None
    bids: tuple[BidRecord, ...] = ()
    contract: ContractInfo | None = None
    current_trick: tuple[PlayedCardInfo, ...] = ()
    last_trick: tuple[PlayedCardInfo, ...] | None = None
    trick_counts: TrickCounts = TrickCounts()
    totals: dict[Username, str] = {}
    pending_seat: SeatIndex | None = None
    prompt: Prompt | None = None
    paused: bool = False
    missing_players: tuple[Username, ...] = ()
    # Stopping a lost round early. Only offered when the contract can no
    # longer be made *and* the payout is already fixed, so agreeing costs
    # nobody anything; see jwies_core.scoring.payout_is_settled.
    folding_offered: bool = False
    folded: tuple[SeatIndex, ...] = ()


# --- client messages ----------------------------------------------------------


class GameAction(ProtocolModel):
    """A move at the table, as opposed to something about the lobby.

    Each one knows how to become the engine's own action type, so a new move
    is one class rather than an entry in three ``match`` statements.
    """

    def to_action(self) -> Action:
        raise NotImplementedError


class Hello(ProtocolModel):
    """First message on every connection.

    ``resume_token`` is what a returning player presents to rebind to a seat.
    The username alone also works when the previous connection is dead.

    ``username`` is a bare ``str``: the one wire field whose contents its type
    does not police. A name that breaks the rules must still *parse*, because a
    rejected envelope is answered with "onbegrijpelijk bericht" - and a player
    who typed one character too few has no way to guess that this is what the
    sentence means. ``_handshake`` asks ``SessionRegistry.is_valid_username``
    instead, which answers ``username_invalid`` and says what the rules are.
    """

    type: Literal["hello"] = "hello"
    username: str
    resume_token: str | None = None


class LobbyList(ProtocolModel):
    type: Literal["lobby_list"] = "lobby_list"


class LobbyCreate(ProtocolModel):
    type: Literal["lobby_create"] = "lobby_create"
    name: Annotated[str, Field(min_length=1, max_length=40)]
    ruleset: str | None = None
    scoring: str | None = None
    # Fixing the seed makes a game reproducible; used by tests and debugging.
    rng_seed: int | None = None


class LobbyJoin(ProtocolModel):
    type: Literal["lobby_join"] = "lobby_join"
    lobby_id: LobbyId


class LobbyLeave(ProtocolModel):
    type: Literal["lobby_leave"] = "lobby_leave"


class LobbyDelete(ProtocolModel):
    type: Literal["lobby_delete"] = "lobby_delete"
    lobby_id: LobbyId


class RequestSnapshot(ProtocolModel):
    type: Literal["request_snapshot"] = "request_snapshot"


class ChatSend(ProtocolModel):
    type: Literal["chat_send"] = "chat_send"
    text: Annotated[str, Field(min_length=1, max_length=500)]


class AnswerShuffle(GameAction):
    type: Literal["answer_shuffle"] = "answer_shuffle"
    shuffle: bool

    def to_action(self) -> Shuffle:
        return Shuffle(shuffle=self.shuffle)


class AnswerCut(GameAction):
    type: Literal["answer_cut"] = "answer_cut"
    count: int

    def to_action(self) -> Cut:
        return Cut(count=self.count)


class PlaceBid(GameAction):
    type: Literal["place_bid"] = "place_bid"
    bid: BidInfo

    def to_action(self) -> PlaceBidAction:
        return PlaceBidAction(
            bid=Bid(type=self.bid.type, tricks=self.bid.tricks, suit=self.bid.suit)
        )


class PlayCard(GameAction):
    type: Literal["play_card"] = "play_card"
    card: CardCode

    def to_action(self) -> PlayCardAction:
        # The pattern on CardCode already rejected anything unparseable.
        return PlayCardAction(card=Card.from_code(self.card))


class FoldVote(GameAction):
    """Agree to stop a lost round early, or take that back.

    The one action not taken in turn: the table is deciding something together.
    Only accepted while ``Snapshot.folding_offered`` is set.
    """

    type: Literal["fold"] = "fold"
    fold: bool = True

    def to_action(self) -> FoldAction:
        return FoldAction(fold=self.fold)


ClientMessage: TypeAlias = Annotated[
    Hello
    | LobbyList
    | LobbyCreate
    | LobbyJoin
    | LobbyLeave
    | LobbyDelete
    | RequestSnapshot
    | ChatSend
    | AnswerShuffle
    | AnswerCut
    | PlaceBid
    | PlayCard
    | FoldVote,
    Field(discriminator="type"),
]


# --- server messages: state ---------------------------------------------------


class HelloOk(ProtocolModel):
    type: Literal["hello_ok"] = "hello_ok"
    username: Username
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


# --- server messages: the trick on the table ----------------------------------


class CardPlayed(ProtocolModel):
    type: Literal["card_played"] = "card_played"
    seat: SeatIndex
    card: CardCode


class TrickCompleted(ProtocolModel):
    type: Literal["trick_completed"] = "trick_completed"
    winner_seat: SeatIndex
    cards: tuple[PlayedCardInfo, ...]
    trick_counts: TrickCounts


class TableCleared(ProtocolModel):
    """Sent after the ruleset's pause, once the trick has been admired."""

    type: Literal["table_cleared"] = "table_cleared"


# --- server messages: announcements -------------------------------------------


class Error(ProtocolModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    text: str  # Dutch, safe to show as-is


class Chat(ProtocolModel):
    type: Literal["chat"] = "chat"
    kind: ChatKind
    text: str
    sender: Username | None = None


class GameStarted(ProtocolModel):
    type: Literal["game_started"] = "game_started"
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
    | PlayerJoined
    | PlayerLeft
    | PlayerDisconnected
    | PlayerReconnected
    | GamePaused
    | GameResumed,
    Field(discriminator="type"),
]


# --- envelopes ----------------------------------------------------------------
#
# A websocket already frames and orders messages, so an envelope only has to
# carry the version and a sequence number.


class ClientEnvelope(ProtocolModel):
    """What a client puts on the wire.

    The only wire model that tolerates unknown fields. A client one version
    behind must still get as far as the version check in ``_handshake`` and be
    told to update - if its stale envelope were rejected outright it would be
    answered with "onbegrijpelijk bericht" instead, which helps nobody.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    v: int = PROTOCOL_VERSION
    msg: ClientMessage


class ServerEnvelope(ProtocolModel):
    """What the server puts on the wire."""

    v: int = PROTOCOL_VERSION
    # Monotonic per connection. A gap means the client missed something and
    # should ask for a fresh snapshot.
    seq: int = 0
    msg: ServerMessage
