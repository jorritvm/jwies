"""Actions a player can take, and events the engine emits in response.

Both are plain frozen dataclasses: the engine never touches a socket, so the
server is free to translate these into protocol messages however it likes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from jwies_core.bidding import Bid
from jwies_core.cards import Card, Suit
from jwies_core.contracts import Contract
from jwies_core.seats import Seat

__all__ = [
    "Action",
    "BidPlaced",
    "BiddingFinished",
    "CardPlayed",
    "CardsDealt",
    "ContractEstablished",
    "ContractLost",
    "Cut",
    "DealerAnnounced",
    "DeckCut",
    "Event",
    "Fold",
    "FoldingChanged",
    "GameFinished",
    "IllegalAction",
    "PlaceBid",
    "PlayCard",
    "RedealRequired",
    "RoundScored",
    "Shuffle",
    "TrickCompleted",
    "TrumpTurned",
]


class IllegalAction(Exception):
    """A player tried something the rules or the phase do not allow.

    The message is Dutch: it is shown to the player as-is.
    """


# --- actions -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Shuffle:
    """The dealer answers whether he wants to shuffle."""

    shuffle: bool


@dataclass(frozen=True, slots=True)
class Cut:
    """The player right of the dealer cuts, taking ``count`` cards."""

    count: int


@dataclass(frozen=True, slots=True)
class PlaceBid:
    bid: Bid


@dataclass(frozen=True, slots=True)
class PlayCard:
    card: Card


@dataclass(frozen=True, slots=True)
class Fold:
    """Vote to stop a lost round early, or withdraw that vote.

    Unlike every other action this one is not taken in turn: the table is
    deciding something together, so any seat may cast or change its vote at any
    moment while the offer stands.
    """

    fold: bool = True


Action = Shuffle | Cut | PlaceBid | PlayCard | Fold


# --- events ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DealerAnnounced:
    round_number: int
    dealer: Seat
    multiplier: Decimal


@dataclass(frozen=True, slots=True)
class DeckCut:
    seat: Seat
    count: int


@dataclass(frozen=True, slots=True)
class CardsDealt:
    packets: tuple[int, ...]
    hands: dict[Seat, tuple[Card, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrumpTurned:
    """The 'geblekte' card that decides the trump suit."""

    dealer: Seat
    card: Card


@dataclass(frozen=True, slots=True)
class BidPlaced:
    seat: Seat
    bid: Bid
    forced: bool = False


@dataclass(frozen=True, slots=True)
class BiddingFinished:
    pass


@dataclass(frozen=True, slots=True)
class RedealRequired:
    reason: str
    next_dealer: Seat


@dataclass(frozen=True, slots=True)
class ContractEstablished:
    contract: Contract
    trump: Suit | None


@dataclass(frozen=True, slots=True)
class CardPlayed:
    seat: Seat
    card: Card
    position_in_trick: int


@dataclass(frozen=True, slots=True)
class TrickCompleted:
    winner: Seat
    cards: tuple[tuple[Seat, Card], ...]
    declarer_tricks: int
    defender_tricks: int


@dataclass(frozen=True, slots=True)
class ContractLost:
    """The contract can no longer be made. Emitted once, the moment it happens.

    Worth saying out loud because what follows is counter-intuitive: the round
    normally carries on, and it still matters. A contract that goes down is paid
    per missing trick, so every trick the declaring side claws back from here
    lowers what they owe. ``folding_offered`` says whether this table is instead
    free to stop, which it only is when the penalty does not vary.
    """

    contract: Contract
    folding_offered: bool


@dataclass(frozen=True, slots=True)
class FoldingChanged:
    """The set of seats willing to stop early has changed."""

    folded: frozenset[Seat]


@dataclass(frozen=True, slots=True)
class RoundScored:
    contract: Contract
    tricks_made: int
    made: bool
    deltas: dict[Seat, Decimal]
    totals: dict[Seat, Decimal]
    # True when the table agreed to stop before the last trick was played.
    folded: bool = False


@dataclass(frozen=True, slots=True)
class GameFinished:
    totals: dict[Seat, Decimal]


Event = (
    DealerAnnounced
    | DeckCut
    | CardsDealt
    | TrumpTurned
    | BidPlaced
    | BiddingFinished
    | RedealRequired
    | ContractEstablished
    | CardPlayed
    | TrickCompleted
    | ContractLost
    | FoldingChanged
    | RoundScored
    | GameFinished
)
