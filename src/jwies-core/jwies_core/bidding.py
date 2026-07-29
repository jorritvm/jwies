"""Bidding: the ladder and what may still be bid.

Replaces ``Table.trickbids`` (three parallel lists of strings) with typed
entries, and ``Table.get_remaining_bid_options`` (a chain of eleven ``elif``
branches over substring membership) with a ladder driven by the ruleset.

The reusable knowledge from the old function is the *order* of the contracts
and the "asked, three passed, asker gets a final say" rule; both survive here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from jwies_core.cards import Suit
from jwies_core.config.ruleset import Ruleset
from jwies_core.contracts import CONTRACT_CATALOG, ContractKey, TrumpSource
from jwies_core.seats import Seat

__all__ = ["Bid", "BidEntry", "BidLadder", "BidType", "bid_to_contract_key"]


class BidType(StrEnum):
    """What a player can say during the bidding round."""

    PASS = "pass"
    ASK = "ask"
    JOIN = "join"
    ALONE = "alone"
    ABONDANCE = "abondance"
    MISERE = "misere"
    MISERE_OUVERTE = "misere_ouverte"
    TROEL = "troel"
    SOLO = "solo"
    SOLO_SLIM = "solo_slim"
    PICO = "pico"


@dataclass(frozen=True, slots=True)
class Bid:
    """A single bid.

    ``tricks`` distinguishes the abondances (9/10/11/12); ``suit`` is only set
    for contracts where the bidder picks the trump himself.
    """

    type: BidType
    tricks: int | None = None
    suit: Suit | None = None

    def __str__(self) -> str:
        parts = [self.type.value]
        if self.tricks is not None:
            parts.append(str(self.tricks))
        if self.suit is not None:
            parts.append(self.suit.value)
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class BidEntry:
    """A bid together with who made it."""

    seat: Seat
    bid: Bid
    forced: bool = False  # de twee automatische troel-biedingen


def bid_to_contract_key(bid: Bid, *, trump_is_turned: bool = False) -> ContractKey | None:
    """The contract a bid would establish, or ``None`` for pass/ask/join."""
    match bid.type:
        case BidType.ALONE:
            return ContractKey.ALONE
        case BidType.MISERE:
            return ContractKey.MISERE
        case BidType.MISERE_OUVERTE:
            return ContractKey.MISERE_OUVERTE
        case BidType.SOLO:
            return ContractKey.SOLO
        case BidType.SOLO_SLIM:
            return ContractKey.SOLO_SLIM
        case BidType.TROEL:
            return ContractKey.TROEL
        case BidType.PICO:
            return ContractKey.PICO
        case BidType.ABONDANCE:
            if bid.tricks == 9 and trump_is_turned:
                return ContractKey.ABONDANCE_9_TRUMP
            return {
                9: ContractKey.ABONDANCE_9,
                10: ContractKey.ABONDANCE_10,
                11: ContractKey.ABONDANCE_11,
                12: ContractKey.ABONDANCE_12,
            }.get(bid.tricks or 0)
        case _:
            return None


def _contract_key_to_bid(key: ContractKey) -> Bid:
    """The bid a player makes to declare ``key``."""
    match key:
        case ContractKey.ALLIANCE:
            return Bid(BidType.ASK)
        case ContractKey.ALONE:
            return Bid(BidType.ALONE)
        case ContractKey.PICO:
            return Bid(BidType.PICO)
        case ContractKey.MISERE:
            return Bid(BidType.MISERE)
        case ContractKey.MISERE_OUVERTE:
            return Bid(BidType.MISERE_OUVERTE)
        case ContractKey.TROEL:
            return Bid(BidType.TROEL)
        case ContractKey.SOLO:
            return Bid(BidType.SOLO)
        case ContractKey.SOLO_SLIM:
            return Bid(BidType.SOLO_SLIM)
        case ContractKey.ABONDANCE_9 | ContractKey.ABONDANCE_9_TRUMP:
            return Bid(BidType.ABONDANCE, tricks=9)
        case ContractKey.ABONDANCE_10:
            return Bid(BidType.ABONDANCE, tricks=10)
        case ContractKey.ABONDANCE_11:
            return Bid(BidType.ABONDANCE, tricks=11)
        case ContractKey.ABONDANCE_12:
            return Bid(BidType.ABONDANCE, tricks=12)
    raise AssertionError(f"onbekend contract: {key}")


class BidLadder:
    """Decides which bids are still available, given a ruleset and the history."""

    def __init__(self, ruleset: Ruleset) -> None:
        self.ruleset = ruleset
        self._order = list(ruleset.bidding.order)

    # --- ranking ----------------------------------------------------------

    def rank_of(self, bid: Bid) -> int | None:
        """Ladder position of a bid, or ``None`` if it does not raise the stakes."""
        if bid.type in (BidType.PASS, BidType.JOIN):
            return None
        if bid.type is BidType.ASK:
            return self.ruleset.rank_of(ContractKey.ALLIANCE)
        key = bid_to_contract_key(bid)
        return None if key is None else self.ruleset.rank_of(key)

    def highest(self, entries: Sequence[BidEntry]) -> BidEntry | None:
        """The entry that currently holds the contract, if any."""
        ranked = [
            (self.rank_of(entry.bid), entry)
            for entry in entries
            if self.rank_of(entry.bid) is not None
        ]
        if not ranked:
            return None
        return max(ranked, key=lambda pair: pair[0])[1]  # type: ignore[arg-type,return-value]

    # --- history helpers --------------------------------------------------

    @staticmethod
    def asker(entries: Sequence[BidEntry]) -> Seat | None:
        for entry in entries:
            if entry.bid.type is BidType.ASK:
                return entry.seat
        return None

    @staticmethod
    def joiner(entries: Sequence[BidEntry]) -> Seat | None:
        for entry in entries:
            if entry.bid.type is BidType.JOIN:
                return entry.seat
        return None

    @staticmethod
    def troel_entries(entries: Sequence[BidEntry]) -> list[BidEntry]:
        return [entry for entry in entries if entry.bid.type is BidType.TROEL]

    def is_final_say(self, entries: Sequence[BidEntry]) -> bool:
        """True when exactly one player asked and the other three passed.

        The asker then chooses: go alone, bid something higher, or pass after
        all - which triggers a redeal. Ported from the old ``get_player_to_bid``.
        """
        voluntary = [entry for entry in entries if not entry.forced]
        if len(voluntary) != 4:
            return False
        passes = sum(1 for entry in voluntary if entry.bid.type is BidType.PASS)
        return self.asker(voluntary) is not None and passes == 3

    # --- the actual question ---------------------------------------------

    def options_after(self, entries: Sequence[BidEntry], seat: Seat) -> list[Bid]:
        """Every bid ``seat`` may legally make right now.

        Always includes ``pass``. The returned list is what the server ships to
        the client in a prompt, so no client - human or AI - ever has to
        reimplement the ladder.
        """
        options: list[Bid] = [Bid(BidType.PASS)]

        troel = self.troel_entries(entries)
        if troel and self.ruleset.bidding.troel_above_all:
            # Only the contracts explicitly allowed to overbid a troel remain.
            for key in self.ruleset.bidding.troel_beaten_by:
                options.append(_contract_key_to_bid(key))
            return options

        current = self.highest(entries)
        floor = 0 if current is None else (self.rank_of(current.bid) or 0) + 1

        for key in self._order:
            if key is ContractKey.ALLIANCE:
                continue  # handled below as ask/join
            rank = self.ruleset.rank_of(key)
            if rank is not None and rank >= floor:
                options.append(_contract_key_to_bid(key))

        asker = self.asker(entries)
        if asker is None:
            alliance_rank = self.ruleset.rank_of(ContractKey.ALLIANCE)
            if alliance_rank is not None and alliance_rank >= floor:
                options.append(Bid(BidType.ASK))
        elif asker != seat and self.joiner(entries) is None:
            options.append(Bid(BidType.JOIN))

        if self.is_final_say(entries) and seat == asker:
            # The asker may no longer ask or join; going alone is what is left.
            options = [
                option for option in options if option.type not in (BidType.ASK, BidType.JOIN)
            ]
            if self.ruleset.rank_of(ContractKey.ALONE) is not None and not any(
                option.type is BidType.ALONE for option in options
            ):
                options.append(Bid(BidType.ALONE))

        # "Alone" promises a ruleset-defined number of tricks (5 or 6); fill it
        # in centrally so every code path offers the same, complete bid.
        options = [
            Bid(BidType.ALONE, tricks=self.ruleset.bidding.alone_tricks)
            if option.type is BidType.ALONE
            else option
            for option in options
        ]

        # Deduplicate while preserving order.
        seen: set[tuple[BidType, int | None]] = set()
        unique: list[Bid] = []
        for option in options:
            marker = (option.type, option.tricks)
            if marker not in seen:
                seen.add(marker)
                unique.append(option)
        return unique

    def needs_suit(self, bid: Bid) -> bool:
        """Whether the bidder must name a trump suit with this bid."""
        key = bid_to_contract_key(bid)
        if key is None:
            return False
        return CONTRACT_CATALOG[key].trump_source is TrumpSource.CHOSEN
