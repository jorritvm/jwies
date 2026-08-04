"""Scoring scale model.

One model expresses both published scales from docs/game/rules.md section 7:
Schaal A (each opponent pays the full amount) and Schaal B (the tabulated value
is the total, split across the opponents). That single ``solo_payment`` enum is
the whole structural difference between them.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from jwies_core.config.base import SCHEMA_VERSION, DutchModel

__all__ = ["ContractScore", "ScoringScale", "SoloPayment"]


class SoloPayment(StrEnum):
    """How a one-against-three contract is settled."""

    PER_OPPONENT = "per_tegenstander"  # Schaal A
    SHARED = "gedeeld"  # Schaal B


class ContractScore(DutchModel):
    """The point values of a single contract."""

    base: Annotated[
        Decimal,
        Field(
            ge=0,
            alias="basis",
            description="Punten wanneer het contract exact gehaald wordt.",
        ),
    ]
    per_overtrick: Annotated[
        Decimal,
        Field(
            ge=0,
            alias="per_overslag",
            description="Extra punten per slag boven het beloofde aantal (0 = geen).",
        ),
    ] = Decimal(0)
    per_undertrick: Annotated[
        Decimal | None,
        Field(
            default=None,
            ge=0,
            alias="per_slag_tekort",
            description=(
                "Punten die per ontbrekende slag betaald worden. "
                "Weglaten = gebruik dezelfde waarde als 'basis'."
            ),
        ),
    ] = None
    all_thirteen: Annotated[
        Decimal | None,
        Field(
            default=None,
            ge=0,
            alias="alle_dertien",
            description=(
                "Vaste waarde wanneer alle 13 slagen gehaald worden. "
                "Weglaten = gewoon basis + per_overslag toepassen."
            ),
        ),
    ] = None

    @property
    def undertrick_value(self) -> Decimal:
        """Points per missing trick, falling back to ``base``."""
        return self.base if self.per_undertrick is None else self.per_undertrick


class ScoringScale(DutchModel):
    """A complete point-counting scale."""

    schema_version: Annotated[
        int,
        Field(alias="schema_versie", description="Versie van het bestandsformaat."),
    ] = SCHEMA_VERSION
    name: Annotated[
        str,
        Field(
            min_length=1,
            alias="naam",
            description="Naam die spelers zien bij het chatcommando !counting.",
        ),
    ]
    solo_payment: Annotated[
        SoloPayment,
        Field(
            alias="betaling_solospel",
            description=(
                "Hoe wordt een contract van een speler tegen drie afgerekend? "
                "per_tegenstander (elke tegenstander betaalt het volle bedrag) of "
                "gedeeld (het bedrag wordt over de drie verdeeld)."
            ),
        ),
    ] = SoloPayment.PER_OPPONENT
    losing_is_double: Annotated[
        bool,
        Field(
            alias="verliezen_is_dubbel",
            description="Kost een mislukt contract het dubbele van de opbrengst?",
        ),
    ] = False
    all_passed_doubles: Annotated[
        bool,
        Field(
            alias="iedereen_past_verdubbelt",
            description="Verdubbelt de inzet van de volgende ronde als iedereen past?",
        ),
    ] = False
    contracts: Annotated[
        dict[str, ContractScore],
        Field(
            alias="contracten",
            min_length=1,
            description="De puntenwaarden per contract.",
        ),
    ]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"schema_versie {self.schema_version} wordt niet ondersteund "
                f"(verwacht: {SCHEMA_VERSION})"
            )
        return self

    def score_for(self, scoring_key: str) -> ContractScore:
        """Look up a contract's values, with a Dutch error when it is missing."""
        try:
            return self.contracts[scoring_key]
        except KeyError:
            raise KeyError(
                f"de puntenschaal '{self.name}' bevat geen waarden voor het "
                f"contract '{scoring_key}'"
            ) from None
