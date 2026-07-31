"""The per-seat snapshot: the complete render contract.

Both clients must be able to draw a full table from a snapshot alone; the
incremental events exist only for animation and chat flavour. That invariant is
what makes reconnect, spectating and a future AI observation vector all fall
out of the same structure.

A snapshot is built per recipient - never broadcast - because it contains the
recipient's hand.
"""

from __future__ import annotations

from jwies_server.protocol.common import (
    BidTypeCode,
    CardCode,
    ContractKeyCode,
    LobbyStatusCode,
    PhaseCode,
    PromptKindCode,
    ProtocolModel,
    SeatIndex,
    SuitCode,
    Username,
)

__all__ = [
    "BidInfo",
    "BidRecord",
    "ContractInfo",
    "LobbyMember",
    "LobbyState",
    "LobbySummary",
    "PlayedCardInfo",
    "Prompt",
    "SeatInfo",
    "Snapshot",
    "TrickCounts",
]


class BidInfo(ProtocolModel):
    """A bid as it travels on the wire."""

    type: BidTypeCode
    tricks: int | None = None
    suit: SuitCode | None = None


class BidRecord(ProtocolModel):
    seat: SeatIndex
    bid: BidInfo
    forced: bool = False
    # Dutch announcement, rendered server-side from the text catalog.
    announcement: str = ""


class PlayedCardInfo(ProtocolModel):
    seat: SeatIndex
    card: CardCode


class ContractInfo(ProtocolModel):
    key: ContractKeyCode
    name: str  # Dutch display name
    tricks_required: int
    declarers: tuple[SeatIndex, ...]
    defenders: tuple[SeatIndex, ...]
    trump: SuitCode | None = None
    open_hand: bool = False


class TrickCounts(ProtocolModel):
    declarers: int = 0
    defenders: int = 0


class SeatInfo(ProtocolModel):
    seat: SeatIndex
    username: Username | None = None
    connected: bool = False
    is_dealer: bool = False
    is_declarer: bool = False
    total: str = "0"  # Decimal as string, to avoid float drift


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

    lobby: LobbyState
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
