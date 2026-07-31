"""Shared primitives of the wire protocol.

The ``*Code`` names are aliases of the engine's own enums, not copies of them.
They used to be a second set of declarations kept honest by a parity test; now
that the protocol lives inside the server - which depends on ``jwies_core``
anyway - the alias *is* the guarantee, and the drift it was guarding against
cannot happen. The names are kept because they read better at the wire boundary
than ``Suit`` or ``Phase`` do.

Neither client imports any of this: both hand-build JSON. That is deliberate,
and it is why the enum values must stay stable strings.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, TypeAlias

from jwies_core.bidding import BidType
from jwies_core.cards import Suit
from jwies_core.contracts import ContractKey
from jwies_core.engine import Phase, PromptKind
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "PROTOCOL_VERSION",
    "BidTypeCode",
    "CardCode",
    "ClientName",
    "ContractKeyCode",
    "LobbyId",
    "LobbyStatusCode",
    "PhaseCode",
    "PromptKindCode",
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
# Which client is on the other end. Logged, never branched on, so it is a plain
# bounded string rather than an enum the server would have to keep in step with
# every front end anyone ever writes.
ClientName: TypeAlias = Annotated[str, Field(max_length=20)]

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
