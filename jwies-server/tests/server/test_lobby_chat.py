"""A command is a question to the table, not a private lookup.

Driven through the lobby's own queue with two seated players, because the
whole point of the behaviour is what the *other* player receives.
"""

from __future__ import annotations

import asyncio

import pytest

from jwies_core.config import Ruleset, ScoringScale
from jwies_server import protocol
from jwies_server.lobby import LobbyRuntime
from jwies_server.sessions import Session


class RecordingAgent:
    """A player agent that keeps everything it was handed."""

    def __init__(self, username: str) -> None:
        self.username = username
        self.delivered: list[protocol.ServerMessage] = []

    async def deliver(self, envelope: protocol.ServerEnvelope) -> None:
        self.delivered.append(envelope.msg)

    async def close(self, code: int, reason: str) -> None:
        pass

    @property
    def chat(self) -> list[str]:
        return [
            message.text for message in self.delivered if isinstance(message, protocol.Chat)
        ]


def player(username: str) -> Session:
    session = Session(username=username)
    session.agent = RecordingAgent(username)
    return session


def heard_by(session: Session) -> list[str]:
    agent = session.agent
    assert isinstance(agent, RecordingAgent)
    return agent.chat


@pytest.fixture
async def table(
    klassiek: Ruleset, schaal_a: ScoringScale
) -> tuple[LobbyRuntime, Session, Session]:
    jan, piet = player("Jan"), player("Piet")
    lobby = LobbyRuntime(
        "tafel-1",
        "De tafel",
        jan,
        ruleset=klassiek,
        ruleset_name="klassiek",
        scoring=schaal_a,
        scoring_name="schaal_a",
    )
    lobby.add_member(piet)
    lobby.start_task()
    try:
        yield lobby, jan, piet
    finally:
        await lobby.stop_task()


async def say(lobby: LobbyRuntime, session: Session, text: str) -> None:
    """Send a line and let the lobby task work through it."""
    lobby.submit(session, protocol.ChatSend(text=text))
    for _ in range(50):
        if lobby._inbox.empty():
            break
        await asyncio.sleep(0)
    await asyncio.sleep(0)


class TestCommandsAreSpokenOutLoud:
    async def test_the_others_see_the_answer(
        self, table: tuple[LobbyRuntime, Session, Session]
    ) -> None:
        lobby, jan, piet = table
        await say(lobby, jan, "!seats")
        assert any("stoel 1" in line for line in heard_by(piet)), heard_by(piet)

    async def test_the_others_see_who_asked(
        self, table: tuple[LobbyRuntime, Session, Session]
    ) -> None:
        lobby, jan, piet = table
        await say(lobby, jan, "!seats")
        assert "!seats" in heard_by(piet)

    async def test_the_asker_still_gets_his_answer(
        self, table: tuple[LobbyRuntime, Session, Session]
    ) -> None:
        lobby, jan, _piet = table
        await say(lobby, jan, "!version")
        assert any("jwies-server" in line for line in heard_by(jan))

    async def test_ordinary_chat_is_unchanged(
        self, table: tuple[LobbyRuntime, Session, Session]
    ) -> None:
        lobby, jan, piet = table
        await say(lobby, jan, "wie speelt er mee?")
        assert heard_by(piet) == ["wie speelt er mee?"]
