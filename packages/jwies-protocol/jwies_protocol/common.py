"""Shared primitives of the wire protocol.

The enums here deliberately duplicate the ones in ``jwies_core``: the protocol
package must stay importable by a client that has no rules engine installed.
``tests/protocol/test_enum_parity.py`` asserts the two sets stay identical, so
the duplication cannot drift.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "PROTOCOL_VERSION",
    "BidTypeCode",
    "CardCode",
    "ClientKind",
    "ContractKeyCode",
    "LobbyId",
    "LobbyStatusCode",
    "PhaseCode",
    "ProtocolModel",
    "SeatIndex",
    "SuitCode",
    "Username",
]

PROTOCOL_VERSION: Final = 1

CardCode: TypeAlias = Annotated[str, Field(pattern=r"^(?:[2-9]|10|[JQKA])[CDHS]$")]
SeatIndex: TypeAlias = Annotated[int, Field(ge=0, le=3)]
LobbyId: TypeAlias = Annotated[str, Field(min_length=1, max_length=64)]
Username: TypeAlias = Annotated[str, Field(pattern=r"^[A-Za-z0-9_\- ]{2,20}$")]


class ProtocolModel(BaseModel):
    """Base for every wire model: strict, immutable, no silent extra fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SuitCode(StrEnum):
    CLUBS = "C"
    DIAMONDS = "D"
    HEARTS = "H"
    SPADES = "S"


class BidTypeCode(StrEnum):
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


class ContractKeyCode(StrEnum):
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


class PhaseCode(StrEnum):
    WAITING_FOR_SHUFFLE = "waiting_for_shuffle"
    WAITING_FOR_CUT = "waiting_for_cut"
    BIDDING = "bidding"
    PLAYING = "playing"
    ROUND_FINISHED = "round_finished"
    GAME_FINISHED = "game_finished"


class LobbyStatusCode(StrEnum):
    WAITING = "waiting"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    BROKEN = "broken"


class ClientKind(StrEnum):
    QT = "qt"
    WEB = "web"
