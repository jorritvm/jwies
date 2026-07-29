"""The player-agent abstraction.

A ``LobbyRuntime`` pulls ``(agent, message)`` pairs off one inbox queue and
cannot tell where a message came from. A websocket connection is one producer;
a future AI player is another, constructed with a ``submit`` callback that puts
messages on the same queue.

That is the whole AI seam. When an AI lands, it implements ``AgentFactory``,
publishes it under the ``jwies.agents`` entry point, and the server gains no
dependency on it.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
from typing import Protocol, runtime_checkable

from jwies_protocol import ClientMessage, ServerEnvelope

__all__ = ["AgentFactory", "PlayerAgent", "load_agent_factories"]

AGENT_ENTRY_POINT_GROUP = "jwies.agents"


@runtime_checkable
class PlayerAgent(Protocol):
    """Anything that can occupy a seat and receive messages."""

    username: str
    is_human: bool

    async def deliver(self, envelope: ServerEnvelope) -> None:
        """Send one message to this agent."""
        ...

    async def close(self, code: int, reason: str) -> None:
        """Tear the agent down."""
        ...


class AgentFactory(Protocol):
    """Creates agents of one kind. Discovered via entry points."""

    name: str

    def create(self, username: str, submit: Callable[[ClientMessage], None]) -> PlayerAgent:
        """Build an agent that submits its decisions through ``submit``."""
        ...


def load_agent_factories() -> dict[str, AgentFactory]:
    """Every agent factory installed in this environment.

    Returns an empty mapping today: no AI ships with jwies. The lookup exists so
    that installing an agent package is the only step needed to enable one.
    """
    factories: dict[str, AgentFactory] = {}
    for entry_point in entry_points(group=AGENT_ENTRY_POINT_GROUP):
        factory = entry_point.load()()
        factories[entry_point.name] = factory
    return factories
