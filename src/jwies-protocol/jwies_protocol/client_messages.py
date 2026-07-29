"""Messages a client sends to the server."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from jwies_protocol.common import (
    CardCode,
    ClientKind,
    LobbyId,
    ProtocolModel,
    Username,
)
from jwies_protocol.snapshot import BidInfo

__all__ = [
    "AnswerCut",
    "AnswerShuffle",
    "ChatSend",
    "ClientMessage",
    "Hello",
    "LobbyCreate",
    "LobbyDelete",
    "LobbyJoin",
    "LobbyLeave",
    "LobbyList",
    "LobbyStart",
    "Ping",
    "PlaceBid",
    "PlayCard",
    "RequestSnapshot",
]


class Hello(ProtocolModel):
    """First message on every connection.

    ``resume_token`` is what a returning player presents to rebind to a seat.
    The username alone also works when the previous connection is dead.
    """

    type: Literal["hello"] = "hello"
    username: Username
    client: ClientKind
    client_version: str = ""
    resume_token: str | None = None


class Ping(ProtocolModel):
    type: Literal["ping"] = "ping"


class LobbyList(ProtocolModel):
    type: Literal["lobby_list"] = "lobby_list"


class LobbyCreate(ProtocolModel):
    type: Literal["lobby_create"] = "lobby_create"
    name: Annotated[str, Field(min_length=1, max_length=40)]
    ruleset: str | None = None
    scoring: str | None = None
    # Fixing the seed makes a game reproducible; used by tests and debugging.
    rng_seed: int | None = None


class LobbyJoin(ProtocolModel):
    type: Literal["lobby_join"] = "lobby_join"
    lobby_id: LobbyId


class LobbyLeave(ProtocolModel):
    type: Literal["lobby_leave"] = "lobby_leave"


class LobbyDelete(ProtocolModel):
    type: Literal["lobby_delete"] = "lobby_delete"
    lobby_id: LobbyId


class LobbyStart(ProtocolModel):
    type: Literal["lobby_start"] = "lobby_start"
    # Name of a registered agent factory used to fill empty seats. No agents
    # ship today; the field is the hook a future AI player plugs into.
    fill_with_agent: str | None = None


class RequestSnapshot(ProtocolModel):
    type: Literal["request_snapshot"] = "request_snapshot"


class ChatSend(ProtocolModel):
    type: Literal["chat_send"] = "chat_send"
    text: Annotated[str, Field(min_length=1, max_length=500)]


class AnswerShuffle(ProtocolModel):
    type: Literal["answer_shuffle"] = "answer_shuffle"
    shuffle: bool


class AnswerCut(ProtocolModel):
    type: Literal["answer_cut"] = "answer_cut"
    count: int


class PlaceBid(ProtocolModel):
    type: Literal["place_bid"] = "place_bid"
    bid: BidInfo


class PlayCard(ProtocolModel):
    type: Literal["play_card"] = "play_card"
    card: CardCode


ClientMessage: TypeAlias = Annotated[
    Hello
    | Ping
    | LobbyList
    | LobbyCreate
    | LobbyJoin
    | LobbyLeave
    | LobbyDelete
    | LobbyStart
    | RequestSnapshot
    | ChatSend
    | AnswerShuffle
    | AnswerCut
    | PlaceBid
    | PlayCard,
    Field(discriminator="type"),
]
