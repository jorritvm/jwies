"""The contract catalogue.

Replaces the 125-line if/elif ladder of the old ``Table.divide_teams`` plus the
threshold chain of ``Table.process_game``. Everything that was code there is
data here: how many tricks a contract promises, where the trump comes from, who
leads, and how many players declare it.

Anything variant-dependent (alone 5 or 6, troel 8 or 9, who leads, which
contracts exist at all) is a ``Ruleset`` lookup layered on top; this catalogue
holds only the invariant shape. Adding pico later is one entry here plus a
position in the ladder - no engine change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

__all__ = [
    "CONTRACT_CATALOG",
    "Contract",
    "ContractKey",
    "ContractSpec",
    "LeadRule",
    "TeamMode",
    "TrumpSource",
]


class ContractKey(StrEnum):
    """Every contract jwies knows about, whether or not a ruleset enables it."""

    ALLIANCE = "alliance"
    ALONE = "alone"
    PICO = "pico"
    ABONDANCE_9 = "abondance_9"
    ABONDANCE_9_TRUMP = "abondance_9_trump"
    ABONDANCE_10 = "abondance_10"
    ABONDANCE_11 = "abondance_11"
    ABONDANCE_12 = "abondance_12"
    MISERE = "misere"
    MISERE_OUVERTE = "misere_ouverte"
    TROEL = "troel"
    SOLO = "solo"
    SOLO_SLIM = "solo_slim"


class TrumpSource(StrEnum):
    """Where the trump suit of a contract comes from."""

    TURNED = "turned"  # de geblekte kaart
    CHOSEN = "chosen"  # de bieder kiest zelf
    NONE = "none"  # zonder troef
    FOURTH_ACE = "fourth_ace"  # troel: de kleur van de vierde aas


class LeadRule(StrEnum):
    """Who plays the first card of the round."""

    LEFT_OF_DEALER = "left_of_dealer"
    DECLARER = "declarer"
    PARTNER = "partner"  # troel: de partner (troel-2) komt uit


class TeamMode(StrEnum):
    """Whether the round is scored as two teams or as declarer(s) versus all."""

    TEAM = "team"
    INDIVIDUAL = "individual"  # meerdere gelijktijdige miseries - nog niet ondersteund


@dataclass(frozen=True, slots=True)
class ContractSpec:
    """The invariant shape of a contract."""

    key: ContractKey
    default_rank: int
    tricks_required: int
    comparison: Literal["at_least", "exactly"]
    declarer_count: int
    trump_source: TrumpSource
    default_lead: LeadRule
    open_hand: bool = False
    team_mode: TeamMode = TeamMode.TEAM
    supported: bool = True

    @property
    def scoring_key(self) -> str:
        """Key under which this contract is looked up in a scoring scale."""
        return self.key.value


def _spec(
    key: ContractKey,
    rank: int,
    tricks: int,
    comparison: Literal["at_least", "exactly"],
    declarers: int,
    trump: TrumpSource,
    lead: LeadRule,
    *,
    open_hand: bool = False,
    supported: bool = True,
) -> ContractSpec:
    return ContractSpec(
        key=key,
        default_rank=rank,
        tricks_required=tricks,
        comparison=comparison,
        declarer_count=declarers,
        trump_source=trump,
        default_lead=lead,
        open_hand=open_hand,
        supported=supported,
    )


# Ranked low to high, following docs/game_rules.md section 4.1. The ranks here
# are defaults: a ruleset re-ranks by listing the contracts in its own order.
CONTRACT_CATALOG: Final[Mapping[ContractKey, ContractSpec]] = {
    spec.key: spec
    for spec in (
        _spec(
            ContractKey.ALLIANCE, 1, 8, "at_least", 2, TrumpSource.TURNED, LeadRule.LEFT_OF_DEALER
        ),
        _spec(ContractKey.ALONE, 2, 5, "at_least", 1, TrumpSource.TURNED, LeadRule.LEFT_OF_DEALER),
        # Pico is modelled but not playable yet: it needs "exactly one trick"
        # bookkeeping the engine does not do. Rulesets that enable it are rejected.
        _spec(
            ContractKey.PICO,
            3,
            1,
            "exactly",
            1,
            TrumpSource.NONE,
            LeadRule.LEFT_OF_DEALER,
            supported=False,
        ),
        _spec(ContractKey.ABONDANCE_9, 4, 9, "at_least", 1, TrumpSource.CHOSEN, LeadRule.DECLARER),
        _spec(
            ContractKey.ABONDANCE_9_TRUMP,
            5,
            9,
            "at_least",
            1,
            TrumpSource.TURNED,
            LeadRule.DECLARER,
        ),
        _spec(ContractKey.MISERE, 6, 0, "exactly", 1, TrumpSource.NONE, LeadRule.DECLARER),
        _spec(
            ContractKey.ABONDANCE_10, 7, 10, "at_least", 1, TrumpSource.CHOSEN, LeadRule.DECLARER
        ),
        _spec(
            ContractKey.ABONDANCE_11, 8, 11, "at_least", 1, TrumpSource.CHOSEN, LeadRule.DECLARER
        ),
        _spec(
            ContractKey.ABONDANCE_12, 9, 12, "at_least", 1, TrumpSource.CHOSEN, LeadRule.DECLARER
        ),
        _spec(ContractKey.TROEL, 10, 8, "at_least", 2, TrumpSource.FOURTH_ACE, LeadRule.PARTNER),
        _spec(
            ContractKey.MISERE_OUVERTE,
            11,
            0,
            "exactly",
            1,
            TrumpSource.NONE,
            LeadRule.DECLARER,
            open_hand=True,
        ),
        _spec(ContractKey.SOLO, 12, 13, "exactly", 1, TrumpSource.CHOSEN, LeadRule.DECLARER),
        _spec(ContractKey.SOLO_SLIM, 13, 13, "exactly", 1, TrumpSource.TURNED, LeadRule.DECLARER),
    )
}


@dataclass(frozen=True, slots=True)
class Contract:
    """A resolved contract for one round, after ruleset overrides are applied."""

    spec: ContractSpec
    declarers: tuple[int, ...]
    defenders: tuple[int, ...]
    trump: object | None  # Suit; typed loosely to keep this module import-light
    tricks_required: int
    leader: int

    @property
    def key(self) -> ContractKey:
        return self.spec.key

    def is_made(self, tricks_by_declarers: int) -> bool:
        """Whether the declaring side fulfilled its promise."""
        if self.spec.comparison == "exactly":
            return tricks_by_declarers == self.tricks_required
        return tricks_by_declarers >= self.tricks_required

    def reachable_tricks(self, taken: int, remaining: int) -> range:
        """Every total the declaring side could still finish on."""
        return range(taken, taken + remaining + 1)

    def can_still_be_made(self, taken: int, remaining: int) -> bool:
        """Whether any way of playing the rest still fulfils the promise.

        Written as a search over the reachable totals rather than as arithmetic,
        so it holds for both comparisons without a special case: a misere dies
        the moment its declarer takes one trick, a solo slim the moment he drops
        one, and both fall out of ``is_made``.
        """
        return any(self.is_made(total) for total in self.reachable_tricks(taken, remaining))
