"""Messages a client sends to the server."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from jwies_core.bidding import Bid
from jwies_core.cards import Card
from jwies_core.events import Action, Cut, Shuffle
from jwies_core.events import PlaceBid as PlaceBidAction
from jwies_core.events import PlayCard as PlayCardAction
from pydantic import Field

from jwies_server.protocol.common import (
    CardCode,
    ClientName,
    LobbyId,
    ProtocolModel,
    Username,
)
from jwies_server.protocol.snapshot import BidInfo

__all__ = [
    "AnswerCut",
    "AnswerShuffle",
    "ChatSend",
    "ClientMessage",
    "GameAction",
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


class GameAction(ProtocolModel):
    """A move at the table, as opposed to something about the lobby.

    Each one knows how to become the engine's own action type. Keeping that
    knowledge on the message removes the translation table the lobby used to
    carry, and means a new move is one class rather than an entry in three
    ``match`` statements.
    """

    def to_action(self) -> Action:
        raise NotImplementedError


class Hello(ProtocolModel):
    """First message on every connection.

    ``resume_token`` is what a returning player presents to rebind to a seat.
    The username alone also works when the previous connection is dead.
    """

    type: Literal["hello"] = "hello"
    username: Username
    client: ClientName
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


class RequestSnapshot(ProtocolModel):
    type: Literal["request_snapshot"] = "request_snapshot"


class ChatSend(ProtocolModel):
    type: Literal["chat_send"] = "chat_send"
    text: Annotated[str, Field(min_length=1, max_length=500)]


class AnswerShuffle(GameAction):
    type: Literal["answer_shuffle"] = "answer_shuffle"
    shuffle: bool

    def to_action(self) -> Shuffle:
        return Shuffle(shuffle=self.shuffle)


class AnswerCut(GameAction):
    type: Literal["answer_cut"] = "answer_cut"
    count: int

    def to_action(self) -> Cut:
        return Cut(count=self.count)


class PlaceBid(GameAction):
    type: Literal["place_bid"] = "place_bid"
    bid: BidInfo

    def to_action(self) -> PlaceBidAction:
        return PlaceBidAction(
            bid=Bid(type=self.bid.type, tricks=self.bid.tricks, suit=self.bid.suit)
        )


class PlayCard(GameAction):
    type: Literal["play_card"] = "play_card"
    card: CardCode

    def to_action(self) -> PlayCardAction:
        # The pattern on CardCode already rejected anything unparseable.
        return PlayCardAction(card=Card.from_code(self.card))


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
