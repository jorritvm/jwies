"""The player-agent abstraction.

A ``LobbyRuntime`` pulls messages off one inbox queue and cannot tell where a
message came from. A websocket connection is one producer; a future AI player
would be another, constructed with a ``submit`` callback that puts messages on
the same queue.

That is the whole AI seam: one protocol describing how ``LobbyRuntime._send``
reaches a seat. A factory, entry-point group or config field can follow once
an actual agent exists to design them around.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from jwies_server.protocol import ServerEnvelope

__all__ = ["PlayerAgent"]


@runtime_checkable
class PlayerAgent(Protocol):
    """Anything that can occupy a seat and receive messages."""

    username: str

    async def deliver(self, envelope: ServerEnvelope) -> None:
        """Send one message to this agent."""
        ...

    async def close(self, code: int, reason: str) -> None:
        """Tear the agent down."""
        ...
