"""Envelopes wrapping every message.

Replaces the old hand-rolled framing (a uint16 length prefix plus two
QDataStream QStrings, all structure via ``split(",")``). A websocket already
frames messages, so an envelope only has to carry versioning, correlation and
ordering.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from jwies_protocol.client_messages import ClientMessage
from jwies_protocol.common import PROTOCOL_VERSION, ProtocolModel
from jwies_protocol.server_messages import ServerMessage

__all__ = ["ClientEnvelope", "ServerEnvelope"]


def _now() -> datetime:
    return datetime.now(UTC)


class ClientEnvelope(ProtocolModel):
    """What a client puts on the wire."""

    v: int = PROTOCOL_VERSION
    # Optional client-chosen id, echoed back in ``ServerEnvelope.re`` so a
    # client can correlate an answer with the request that caused it.
    id: str | None = None
    msg: ClientMessage


class ServerEnvelope(ProtocolModel):
    """What the server puts on the wire."""

    v: int = PROTOCOL_VERSION
    # Monotonic per connection. A gap means the client missed something and
    # should ask for a fresh snapshot.
    seq: int = 0
    re: str | None = None
    ts: datetime = Field(default_factory=_now)
    msg: ServerMessage
