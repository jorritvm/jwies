"""Turning a finished bidding round into a contract.

A lookup in ``CONTRACT_CATALOG``: the differences between contracts are data,
so adding a contract is a data change, not a code change.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from jwies_core.bidding import Bid, BidEntry, BidLadder, BidType, bid_to_contract_key
from jwies_core.cards import Card, Suit
from jwies_core.config.ruleset import Ruleset
from jwies_core.contracts import (
    CONTRACT_CATALOG,
    Contract,
    ContractKey,
    LeadRule,
    TrumpSource,
)
from jwies_core.seats import ALL_SEATS, Seat, left_of
from jwies_core.troel import TroelResult

__all__ = ["RedealReason", "ResolutionError", "resolve_contract"]


class RedealReason(StrEnum):
    """Why a round produced no contract."""

    ALL_PASSED = "all_passed"
    ASK_DECLINED = "ask_declined"


class ResolutionError(Exception):
    """The bidding history cannot be turned into a contract."""


@dataclass(frozen=True, slots=True)
class _Winner:
    seat: Seat
    bid: Bid
    key: ContractKey


def _find_winner(
    entries: Sequence[BidEntry], ladder: BidLadder, *, turned_trump: Card | None
) -> _Winner | None:
    entry = ladder.highest(entries)
    if entry is None:
        return None
    key = bid_to_contract_key(
        entry.bid,
        trump_is_turned=_abondance_uses_turned_trump(entry.bid, ladder.ruleset),
    )
    if key is None:
        # ``highest`` only ranks contract-establishing bids, so ASK is the only
        # way to get here: it establishes the alliance contract.
        if entry.bid.type is BidType.ASK:
            key = ContractKey.ALLIANCE
        else:
            raise ResolutionError(f"bod zonder contract: {entry.bid}")
    return _Winner(seat=entry.seat, bid=entry.bid, key=key)


def _abondance_uses_turned_trump(bid: Bid, ruleset: Ruleset) -> bool:
    """Whether a 9-trick abondance means "abondance in troef" in this ruleset."""
    if bid.type is not BidType.ABONDANCE or bid.tricks != 9:
        return False
    return (
        ruleset.rank_of(ContractKey.ABONDANCE_9) is None
        and ruleset.rank_of(ContractKey.ABONDANCE_9_TRUMP) is not None
    )


def _declarers(
    key: ContractKey,
    winner: _Winner,
    entries: Sequence[BidEntry],
    ladder: BidLadder,
    troel: TroelResult | None,
) -> tuple[Seat, ...]:
    if key is ContractKey.ALLIANCE:
        asker = ladder.asker(entries)
        joiner = ladder.joiner(entries)
        if asker is None or joiner is None:
            raise ResolutionError("een alliantie vereist zowel een vrager als een meegaander")
        return (asker, joiner)
    if key is ContractKey.TROEL:
        if troel is None:
            raise ResolutionError("troelcontract zonder troeluitslag")
        return (troel.lead, troel.partner)
    return (winner.seat,)


def _trump(
    key: ContractKey,
    winner: _Winner,
    turned_trump: Card | None,
    troel: TroelResult | None,
) -> Suit | None:
    source = CONTRACT_CATALOG[key].trump_source
    match source:
        case TrumpSource.NONE:
            return None
        case TrumpSource.CHOSEN:
            return winner.bid.suit
        case TrumpSource.FOURTH_ACE:
            if troel is None:
                raise ResolutionError("troelcontract zonder troeluitslag")
            return troel.trump
        case TrumpSource.TURNED:
            if turned_trump is None:
                raise ResolutionError(
                    f"contract '{key.value}' speelt met de geblekte troef, "
                    "maar er is geen troefkaart"
                )
            return turned_trump.suit
    raise AssertionError(f"onbekende troefbron: {source}")


def _leader(rule: LeadRule, declarers: tuple[Seat, ...], dealer: Seat) -> Seat:
    match rule:
        case LeadRule.LEFT_OF_DEALER:
            return left_of(dealer)
        case LeadRule.DECLARER:
            return declarers[0]
        case LeadRule.PARTNER:
            # Troel: the partner (the fourth ace) opens.
            return declarers[1] if len(declarers) > 1 else declarers[0]
    raise AssertionError(f"onbekende uitkomregel: {rule}")


def resolve_contract(
    entries: Sequence[BidEntry],
    ladder: BidLadder,
    ruleset: Ruleset,
    *,
    dealer: Seat,
    turned_trump: Card | None,
    troel: TroelResult | None = None,
) -> Contract | RedealReason:
    """Turn a completed bidding round into a contract, or say why we redeal."""
    winner = _find_winner(entries, ladder, turned_trump=turned_trump)

    # An ask that nobody joined is not a contract. The asker was offered the
    # final say and chose not to go alone, so the hand is dead and we redeal
    # with the next dealer.
    if winner is not None and winner.key is ContractKey.ALLIANCE and ladder.joiner(entries) is None:
        return RedealReason.ASK_DECLINED

    if winner is None:
        # Nobody claimed anything. Whether an ask was withdrawn changes which
        # player deals next, so the two cases stay distinguishable.
        asked = any(entry.bid.type is BidType.ASK for entry in entries)
        return RedealReason.ASK_DECLINED if asked else RedealReason.ALL_PASSED

    key = winner.key
    spec = CONTRACT_CATALOG[key]
    if not spec.supported:
        raise ResolutionError(f"contract '{key.value}' is nog niet ondersteund")

    declarers = _declarers(key, winner, entries, ladder, troel)
    defenders = tuple(seat for seat in ALL_SEATS if seat not in declarers)
    trump = _trump(key, winner, turned_trump, troel)
    leader = _leader(ruleset.lead_rule_for(key), declarers, dealer)

    return Contract(
        spec=spec,
        declarers=tuple(int(seat) for seat in declarers),
        defenders=tuple(int(seat) for seat in defenders),
        trump=trump,
        tricks_required=ruleset.tricks_required_for(key),
        leader=int(leader),
    )
