"""One websocket connection: reader task, writer task, and the hello handshake.

The writer owns its own queue so a slow client can never block the game loop.
If that queue overflows the connection is dropped; the player reconnects and
gets a fresh snapshot, which costs nothing because the snapshot is the complete
render contract.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import WebSocket
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect, WebSocketState

from jwies_server import __version__
from jwies_server.lobby_manager import LobbyError, LobbyManager
from jwies_server.protocol import (
    PROTOCOL_VERSION,
    ClientEnvelope,
    ErrorCode,
    ServerEnvelope,
    ServerMessage,
    client_messages,
    server_messages,
)
from jwies_server.sessions import HelloOutcome, Session, SessionRegistry

__all__ = ["WebsocketAgent", "handle_connection"]

log = logging.getLogger(__name__)

WRITE_QUEUE_LIMIT = 256
CLOSE_PROTOCOL_VERSION = 4400
CLOSE_USERNAME_TAKEN = 4409


class WebsocketAgent:
    """A ``PlayerAgent`` backed by a websocket."""

    def __init__(self, websocket: WebSocket, username: str) -> None:
        self.websocket = websocket
        self.username = username
        self._queue: asyncio.Queue[ServerEnvelope | None] = asyncio.Queue(maxsize=WRITE_QUEUE_LIMIT)
        self._seq = 0
        self._writer: asyncio.Task[None] | None = None
        self.overflowed = False

    def start(self) -> None:
        self._writer = asyncio.create_task(self._run_writer(), name=f"tx-{self.username}")

    async def deliver(self, envelope: ServerEnvelope) -> None:
        self._seq += 1
        stamped = envelope.model_copy(update={"seq": self._seq})
        try:
            self._queue.put_nowait(stamped)
        except asyncio.QueueFull:
            # Too far behind to catch up; drop it and let it reconnect.
            self.overflowed = True
            log.warning("schrijfwachtrij vol voor %s, verbinding wordt gesloten", self.username)
            with contextlib.suppress(Exception):
                await self.websocket.close(code=1013)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        with contextlib.suppress(Exception):
            self._queue.put_nowait(None)
        if self._writer is not None:
            with contextlib.suppress(asyncio.CancelledError):
                self._writer.cancel()
                await self._writer
            self._writer = None
        if self.websocket.client_state is WebSocketState.CONNECTED:
            with contextlib.suppress(Exception):
                await self.websocket.close(code=code, reason=reason)

    async def _run_writer(self) -> None:
        while True:
            envelope = await self._queue.get()
            if envelope is None:
                return
            if self.websocket.client_state is not WebSocketState.CONNECTED:
                return
            try:
                await self.websocket.send_text(envelope.model_dump_json())
            except (WebSocketDisconnect, RuntimeError):
                return


async def _send_raw(websocket: WebSocket, message: ServerMessage) -> None:
    """Send before an agent exists (during the handshake)."""
    with contextlib.suppress(Exception):
        await websocket.send_text(ServerEnvelope(msg=message).model_dump_json())


async def handle_connection(
    websocket: WebSocket,
    *,
    sessions: SessionRegistry,
    lobbies: LobbyManager,
) -> None:
    """Run one connection from accept to close."""
    await websocket.accept()
    session: Session | None = None
    agent: WebsocketAgent | None = None

    try:
        session, agent = await _handshake(websocket, sessions, lobbies)
        if session is None or agent is None:
            return

        while True:
            raw = await websocket.receive_text()
            envelope = _parse(raw)
            if envelope is None:
                await _send_raw(
                    websocket,
                    server_messages.Error(
                        code=ErrorCode.BAD_MESSAGE,
                        text="Onbegrijpelijk bericht ontvangen.",
                    ),
                )
                continue
            await _route(envelope, session, lobbies)

    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("verbindingsfout")
    finally:
        if session is not None:
            session.disconnect()
            lobby = lobbies.lobby_of(session)
            if lobby is not None:
                with contextlib.suppress(Exception):
                    await lobby.on_disconnected(session)
        if agent is not None:
            await agent.close()


def _parse(raw: str) -> ClientEnvelope | None:
    try:
        return ClientEnvelope.model_validate_json(raw)
    except ValidationError:
        return None


async def _handshake(
    websocket: WebSocket,
    sessions: SessionRegistry,
    lobbies: LobbyManager,
) -> tuple[Session | None, WebsocketAgent | None]:
    raw = await websocket.receive_text()
    envelope = _parse(raw)

    if envelope is None or not isinstance(envelope.msg, client_messages.Hello):
        await _send_raw(
            websocket,
            server_messages.Error(
                code=ErrorCode.BAD_MESSAGE, text="Onbegrijpelijk bericht ontvangen."
            ),
        )
        await websocket.close()
        return None, None

    if envelope.v != PROTOCOL_VERSION:
        await _send_raw(
            websocket,
            server_messages.Error(
                code=ErrorCode.PROTOCOL_VERSION,
                text=(
                    f"Deze client spreekt versie {envelope.v} van het protocol, "
                    f"de server versie {PROTOCOL_VERSION}. Werk je client bij."
                ),
            ),
        )
        await websocket.close(code=CLOSE_PROTOCOL_VERSION)
        return None, None

    hello = envelope.msg
    if not sessions.is_valid_username(hello.username):
        await _send_raw(
            websocket,
            server_messages.Error(
                code=ErrorCode.USERNAME_INVALID,
                text=("Ongeldige naam. Gebruik 2 tot 20 letters, cijfers, spaties, '-' of '_'."),
            ),
        )
        await websocket.close(code=CLOSE_USERNAME_TAKEN)
        return None, None

    session, outcome = sessions.resolve_hello(hello.username, hello.resume_token)
    if outcome is HelloOutcome.TAKEN:
        await _send_raw(
            websocket,
            server_messages.Error(
                code=ErrorCode.USERNAME_TAKEN,
                text=(f"De naam '{hello.username}' is al in gebruik door iemand die online is."),
            ),
        )
        await websocket.close(code=CLOSE_USERNAME_TAKEN)
        return None, None

    agent = WebsocketAgent(websocket, session.username)
    agent.start()
    session.agent = agent
    session.touch()

    await agent.deliver(
        ServerEnvelope(
            re=envelope.id,
            msg=server_messages.HelloOk(
                player_id=session.player_id,
                username=session.username,
                server_version=__version__,
                protocol_version=PROTOCOL_VERSION,
                resume_token=session.resume_token,
                current_lobby=session.lobby_id,
                rulesets=tuple(sorted(lobbies.config.rulesets)),
                scorings=tuple(sorted(lobbies.config.scorings)),
            ),
        )
    )

    lobby = lobbies.lobby_of(session)
    if lobby is not None and outcome in (HelloOutcome.RESUMED, HelloOutcome.REBOUND):
        await lobby.on_reconnected(session)
    else:
        await agent.deliver(
            ServerEnvelope(
                msg=server_messages.Chat(
                    kind=server_messages.ChatKind.SERVER,
                    text=f"Welkom {session.username}!",
                    private=True,
                )
            )
        )
    return session, agent


async def _route(
    envelope: ClientEnvelope,
    session: Session,
    lobbies: LobbyManager,
) -> None:
    """Handle lobby-level messages here; hand game messages to the lobby task."""
    message = envelope.msg
    session.touch()

    async def reply(payload: ServerMessage) -> None:
        if session.agent is not None:
            await session.agent.deliver(ServerEnvelope(msg=payload, re=envelope.id))

    try:
        match message:
            case client_messages.Ping():
                await reply(server_messages.Pong())

            case client_messages.Hello():
                # A second hello on a live connection is meaningless; ignore it
                # rather than tearing down a working session.
                return

            case client_messages.LobbyList():
                await reply(server_messages.LobbyListing(lobbies=lobbies.list_summaries()))

            case client_messages.LobbyCreate():
                lobby = lobbies.create(
                    session,
                    message.name,
                    ruleset=message.ruleset,
                    scoring=message.scoring,
                    rng_seed=message.rng_seed,
                )
                await reply(server_messages.LobbyStateMessage(lobby=lobby.lobby_state()))
                await lobby.broadcast(
                    server_messages.PlayerJoined(username=session.username, seat=session.seat)
                )

            case client_messages.LobbyJoin():
                lobby = lobbies.join(session, message.lobby_id)
                await reply(server_messages.LobbyStateMessage(lobby=lobby.lobby_state()))
                await lobby.broadcast(
                    server_messages.PlayerJoined(username=session.username, seat=session.seat)
                )
                await lobby.broadcast(server_messages.LobbyStateMessage(lobby=lobby.lobby_state()))
                await lobby.broadcast(lobby.presenter.chat(f"{session.username} komt aan tafel."))
                if lobbies.is_startable(lobby):
                    await lobby.start_game()

            case client_messages.LobbyLeave():
                lobby = lobbies.leave(session)
                if lobby is not None:
                    await lobby.broadcast(server_messages.PlayerLeft(username=session.username))
                    await lobby.broadcast(
                        server_messages.LobbyStateMessage(lobby=lobby.lobby_state())
                    )

            case client_messages.LobbyDelete():
                await lobbies.delete(session, message.lobby_id)
                await reply(server_messages.LobbyListing(lobbies=lobbies.list_summaries()))

            case _:
                lobby = lobbies.lobby_of(session)
                if lobby is None:
                    await reply(
                        server_messages.Error(
                            code=ErrorCode.NOT_IN_LOBBY,
                            text="Je zit niet in een lobby.",
                        )
                    )
                    return
                lobby.submit(session, message, correlation=envelope.id)

    except LobbyError as error:
        await reply(
            server_messages.Error(code=error.code, text=error.text)  # type: ignore[arg-type]
        )
