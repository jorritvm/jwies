"""Ruleset model - which variant of Vlaamse wies a lobby plays.

Every field carries a ``description`` that mirrors the comment above the same
key in the YAML templates. ``!ruleset`` in chat renders those descriptions, and
a test keeps the two in sync.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from jwies_core.cards import CARDS_PER_HAND
from jwies_core.config.base import SCHEMA_VERSION, DutchModel
from jwies_core.contracts import CONTRACT_CATALOG, ContractKey, LeadRule

__all__ = ["AllPassedRule", "BidSettings", "DealSettings", "PlaySettings", "Ruleset"]


class AllPassedRule(StrEnum):
    """What happens when all four players pass."""

    REDEAL = "herdelen"
    NEXT_ROUND_DOUBLE = "volgende_ronde_dubbel"
    QUEENS = "dames_rapen"  # niet ondersteund


class DealSettings(DutchModel):
    packets: Annotated[
        list[Annotated[int, Field(ge=1, le=CARDS_PER_HAND)]],
        Field(
            alias="pakjes",
            min_length=1,
            description=(
                "Grootte van elk pakje dat de deler uitdeelt, in volgorde. "
                "De som moet exact 13 zijn. Klassiek is [4, 4, 5]; "
                "veel clubs delen [3, 3, 3, 4]."
            ),
        ),
    ]
    dealer_may_shuffle: Annotated[
        bool,
        Field(
            alias="deler_mag_schudden",
            description=(
                "Mag de deler het pak schudden voor hij deelt? In het traditionele "
                "wiezen wordt enkel voor het allereerste spel geschud."
            ),
        ),
    ] = False
    cut_minimum: Annotated[
        int,
        Field(
            ge=1,
            le=51,
            alias="coupeer_minimum",
            description="Minimum aantal kaarten dat de coupeur mag afnemen (1 t.e.m. 51).",
        ),
    ] = 4
    cut_maximum: Annotated[
        int,
        Field(
            ge=1,
            le=51,
            alias="coupeer_maximum",
            description="Maximum aantal kaarten dat de coupeur mag afnemen (1 t.e.m. 51).",
        ),
    ] = 48

    @model_validator(mode="after")
    def _check(self) -> Self:
        total = sum(self.packets)
        if total != CARDS_PER_HAND:
            raise ValueError(f"de som van de pakjes moet exact {CARDS_PER_HAND} zijn (nu {total})")
        if self.cut_minimum >= self.cut_maximum:
            raise ValueError(
                f"coupeer_minimum ({self.cut_minimum}) moet kleiner zijn dan "
                f"coupeer_maximum ({self.cut_maximum})"
            )
        return self


class BidSettings(DutchModel):
    order: Annotated[
        list[ContractKey],
        Field(
            alias="volgorde",
            min_length=1,
            description=(
                "Welke contracten geboden mogen worden, van laag naar hoog. "
                "Contracten die je weglaat, bestaan niet in dit spel."
            ),
        ),
    ]
    troel_above_all: Annotated[
        bool,
        Field(
            alias="troel_boven_alles",
            description=(
                "Staat troel boven alle andere contracten? Dan wordt er na een troel "
                "niet verder geboden, tenzij via 'troel_kan_overboden_worden_door'."
            ),
        ),
    ] = True
    troel_beaten_by: Annotated[
        list[ContractKey],
        Field(
            alias="troel_kan_overboden_worden_door",
            description=(
                "Welke contracten mogen een troel toch nog overtroeven? "
                "Enkel van toepassing wanneer troel_boven_alles true is."
            ),
        ),
    ] = []
    alone_tricks: Annotated[
        int,
        Field(
            ge=5,
            le=6,
            alias="slagen_bij_alleen_gaan",
            description=(
                "Hoeveel slagen belooft wie alleen gaat? In Vlaanderen meestal 5, elders 6."
            ),
        ),
    ] = 5
    troel_tricks: Annotated[
        int,
        Field(
            ge=8,
            le=9,
            alias="slagen_bij_troel",
            description=(
                "Hoeveel slagen belooft een troelduo? Bij open troel meestal 8, "
                "bij gesloten troel meestal 9."
            ),
        ),
    ] = 8
    all_passed: Annotated[
        AllPassedRule,
        Field(
            alias="iedereen_past",
            description=(
                "Wat gebeurt er als iedereen past? herdelen, volgende_ronde_dubbel "
                "of dames_rapen (nog niet ondersteund)."
            ),
        ),
    ] = AllPassedRule.REDEAL

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(set(self.order)) != len(self.order):
            raise ValueError("volgorde bevat een dubbel contract")
        unsupported = [key for key in self.order if not CONTRACT_CATALOG[key].supported]
        if unsupported:
            names = ", ".join(sorted(key.value for key in unsupported))
            raise ValueError(f"nog niet ondersteunde contracten in volgorde: {names}")
        unknown = [key for key in self.troel_beaten_by if key not in self.order]
        if unknown:
            names = ", ".join(sorted(key.value for key in unknown))
            raise ValueError(
                f"troel_kan_overboden_worden_door verwijst naar contracten die niet "
                f"in 'volgorde' staan: {names}"
            )
        if self.all_passed is AllPassedRule.QUEENS:
            raise ValueError(
                "iedereen_past: 'dames_rapen' is nog niet ondersteund; "
                "kies 'herdelen' of 'volgende_ronde_dubbel'"
            )
        return self


class LeadSettings(DutchModel):
    """Whether the declarer leads, per contract family."""

    abondance: Annotated[bool, Field(description="Komt de abondance-speler zelf uit?")] = True
    misere: Annotated[bool, Field(description="Komt de miseriespeler zelf uit?")] = True
    misere_ouverte: Annotated[
        bool, Field(description="Komt de speler van miserie bloot zelf uit?")
    ] = True
    solo: Annotated[bool, Field(description="Komt de solospeler zelf uit?")] = True
    solo_slim: Annotated[bool, Field(description="Komt de solo slim-speler zelf uit?")] = True
    troel: Annotated[bool, Field(description="Komt bij troel de partner (de vierde aas) uit?")] = (
        True
    )


class PlaySettings(DutchModel):
    troel_must_lead_highest_trump: Annotated[
        bool,
        Field(
            alias="hoogste_troef_verplicht_bij_troel",
            description=(
                "Moet de troelspeler zijn hoogste troef als eerste kaart spelen? "
                "Klassieke afspraak wanneer er 8 slagen gevraagd worden."
            ),
        ),
    ] = True
    pause_after_trick_seconds: Annotated[
        float,
        Field(
            ge=0,
            le=15,
            alias="pauze_na_slag_seconden",
            description="Hoeveel seconden blijft een volle slag op tafel liggen?",
        ),
    ] = 2.0
    folding_allowed: Annotated[
        bool,
        Field(
            alias="opgeven_toegelaten",
            description=(
                "Mag de tafel een verloren ronde vroegtijdig stoppen? "
                "Enkel wanneer het contract niet meer gehaald kan worden en de "
                "punten al vastliggen, en enkel als alle vier de spelers akkoord "
                "gaan. De kaarten worden dan opgeraapt zoals ze liggen."
            ),
        ),
    ] = True
    round_count: Annotated[
        int,
        Field(
            ge=0,
            alias="aantal_rondes",
            description=(
                "Aantal rondes voor het spel eindigt. 0 = eindeloos doorspelen. "
                "Kies een veelvoud van 4 zodat iedereen even vaak deelt."
            ),
        ),
    ] = 0


class Ruleset(DutchModel):
    """The complete set of house rules a lobby plays by."""

    schema_version: Annotated[
        int,
        Field(alias="schema_versie", description="Versie van het bestandsformaat."),
    ] = SCHEMA_VERSION
    name: Annotated[
        str,
        Field(
            min_length=1,
            alias="naam",
            description="Naam die spelers zien in de lobby en bij het commando !ruleset.",
        ),
    ]
    deal: Annotated[DealSettings, Field(alias="delen", description="Instellingen rond delen.")]
    bidding: Annotated[BidSettings, Field(alias="bieden", description="Instellingen rond bieden.")]
    lead: Annotated[
        LeadSettings, Field(alias="uitkomen", description="Wie komt uit per contract.")
    ] = LeadSettings()
    play: Annotated[
        PlaySettings, Field(alias="spel", description="Instellingen tijdens het spelen.")
    ] = PlaySettings()

    @model_validator(mode="after")
    def _check_schema_version(self) -> Self:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"schema_versie {self.schema_version} wordt niet ondersteund "
                f"(verwacht: {SCHEMA_VERSION})"
            )
        return self

    def tricks_required_for(self, key: ContractKey) -> int:
        """Trick target for a contract, after applying this ruleset's overrides."""
        if key is ContractKey.ALONE:
            return self.bidding.alone_tricks
        if key is ContractKey.TROEL:
            return self.bidding.troel_tricks
        return CONTRACT_CATALOG[key].tricks_required

    def lead_rule_for(self, key: ContractKey) -> LeadRule:
        """Who leads the first trick under this contract."""
        spec = CONTRACT_CATALOG[key]
        declarer_leads = {
            ContractKey.ABONDANCE_9: self.lead.abondance,
            ContractKey.ABONDANCE_9_TRUMP: self.lead.abondance,
            ContractKey.ABONDANCE_10: self.lead.abondance,
            ContractKey.ABONDANCE_11: self.lead.abondance,
            ContractKey.ABONDANCE_12: self.lead.abondance,
            ContractKey.MISERE: self.lead.misere,
            ContractKey.MISERE_OUVERTE: self.lead.misere_ouverte,
            ContractKey.SOLO: self.lead.solo,
            ContractKey.SOLO_SLIM: self.lead.solo_slim,
        }
        if key is ContractKey.TROEL:
            return LeadRule.PARTNER if self.lead.troel else LeadRule.LEFT_OF_DEALER
        if key in declarer_leads:
            return LeadRule.DECLARER if declarer_leads[key] else LeadRule.LEFT_OF_DEALER
        return spec.default_lead

    def rank_of(self, key: ContractKey) -> int | None:
        """Position on this ruleset's bidding ladder, or ``None`` if disabled."""
        try:
            return self.bidding.order.index(key)
        except ValueError:
            return None
