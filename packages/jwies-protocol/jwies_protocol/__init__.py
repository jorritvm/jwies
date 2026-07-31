"""Wire protocol between the jwies server and its clients.

Pydantic models only: no game logic, and no import of ``jwies_core``. The
server and the PyQt client both depend on this package so the two Python sides
cannot drift; the browser client mirrors the same shapes in plain JSON.

The enums here deliberately duplicate those in ``jwies_core`` so a client needs
no rules engine installed. ``tests/protocol/test_enum_parity.py`` asserts the
two stay identical.
"""

from jwies_protocol import client_messages, server_messages
from jwies_protocol.client_messages import ClientMessage
from jwies_protocol.common import (
    PROTOCOL_VERSION,
    BidTypeCode,
    CardCode,
    ClientKind,
    ContractKeyCode,
    LobbyStatusCode,
    PhaseCode,
    ProtocolModel,
    SeatIndex,
    SuitCode,
    Username,
)
from jwies_protocol.envelope import ClientEnvelope, ServerEnvelope
from jwies_protocol.errors import ErrorCode
from jwies_protocol.server_messages import ChatKind, ServerMessage
from jwies_protocol.snapshot import (
    BidInfo,
    BidRecord,
    ContractInfo,
    LobbyMember,
    LobbyState,
    LobbySummary,
    PlayedCardInfo,
    Prompt,
    PromptKindCode,
    SeatInfo,
    Snapshot,
    TrickCounts,
)

__all__ = [
    "PROTOCOL_VERSION",
    "BidInfo",
    "BidRecord",
    "BidTypeCode",
    "CardCode",
    "ChatKind",
    "ClientEnvelope",
    "ClientKind",
    "ClientMessage",
    "ContractInfo",
    "ContractKeyCode",
    "ErrorCode",
    "LobbyMember",
    "LobbyState",
    "LobbyStatusCode",
    "LobbySummary",
    "PhaseCode",
    "PlayedCardInfo",
    "Prompt",
    "PromptKindCode",
    "ProtocolModel",
    "SeatIndex",
    "SeatInfo",
    "ServerEnvelope",
    "ServerMessage",
    "Snapshot",
    "SuitCode",
    "TrickCounts",
    "Username",
    "client_messages",
    "server_messages",
]
