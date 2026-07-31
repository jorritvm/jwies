"""Wire protocol between the jwies server and its clients.

Pydantic models describing every message that crosses the socket. The server
validates everything on the way in and constructs everything on the way out
from these types, so an unknown message is a validation error rather than a
silently ignored one.

Neither client imports this. Both the PyQt and the browser client hand-build
JSON dicts and read raw dicts back; the models are the server's own contract,
not a library two parties share. That is why the enum *values* are load-bearing
and the class names are not, and why this lives inside ``jwies_server`` rather
than in a package of its own.
"""

from jwies_server.protocol import client_messages, server_messages
from jwies_server.protocol.client_messages import ClientMessage
from jwies_server.protocol.common import (
    PROTOCOL_VERSION,
    BidTypeCode,
    CardCode,
    ClientName,
    ContractKeyCode,
    LobbyStatusCode,
    PhaseCode,
    PromptKindCode,
    ProtocolModel,
    SeatIndex,
    SuitCode,
    Username,
)
from jwies_server.protocol.envelope import ClientEnvelope, ServerEnvelope
from jwies_server.protocol.errors import ErrorCode
from jwies_server.protocol.server_messages import ChatKind, ServerMessage
from jwies_server.protocol.snapshot import (
    BidInfo,
    BidRecord,
    ContractInfo,
    LobbyMember,
    LobbyState,
    LobbySummary,
    PlayedCardInfo,
    Prompt,
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
    "ClientMessage",
    "ClientName",
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
