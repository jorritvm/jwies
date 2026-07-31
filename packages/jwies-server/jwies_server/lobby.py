"""One lobby: a table, its players, and the game running on it.

All engine mutation happens inside a single asyncio task fed by one inbox
queue, so there are no locks anywhere and message ordering is deterministic. A
websocket connection and (later) an AI agent are both just producers on that
queue - the runtime cannot tell them apart.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from dataclasses import dataclass

from jwies_core.config import Ruleset, ScoringScale
from jwies_core.engine import GameEngine, Phase, PromptKind
from jwies_core.events import (
    Event,
    IllegalAction,
    TrickCompleted,
)
from jwies_core.seats import ALL_SEATS, Seat

from jwies_server.chat import ChatContext, handle_chat_command, is_command
from jwies_server.presenter import Presenter
from jwies_server.protocol import (
    ChatKind,
    ClientMessage,
    ErrorCode,
    LobbyMember,
    LobbyState,
    LobbyStatusCode,
    LobbySummary,
    ServerEnvelope,
    ServerMessage,
    Snapshot,
    client_messages,
    server_messages,
)
from jwies_server.sessions import Session
from jwies_server.snapshot import Occupant, build_snapshot, seat_infos

__all__ = ["LobbyRuntime"]

log = logging.getLogger(__name__)

SEAT_COUNT = len(ALL_SEATS)


@dataclass
class Member:
    """A player who has joined this lobby."""

    session: Session
    seat: int | None = None
    is_host: bool = False

    @property
    def username(self) -> str:
        return self.session.username

    @property
    def connected(self) -> bool:
        return self.session.connected


@dataclass
class _Inbound:
    session: Session
    message: ClientMessage
    correlation: str | None = None


class LobbyRuntime:
    """A single table. Owns a ``GameEngine`` and everything around it."""

    def __init__(
        self,
        lobby_id: str,
        name: str,
        host: Session,
        *,
        ruleset: Ruleset,
        ruleset_name: str,
        scoring: ScoringScale,
        scoring_name: str,
        rng_seed: int | None = None,
        pause_after_trick: float | None = None,
    ) -> None:
        self.id = lobby_id
        self.name = name
        self.ruleset = ruleset
        self.ruleset_name = ruleset_name
        self.scoring = scoring
        self.scoring_name = scoring_name
        self.rng_seed = rng_seed
        self.status = LobbyStatusCode.WAITING

        self.members: dict[str, Member] = {}
        self.host_username = host.username
        self.missing: set[str] = set()
        self.engine: GameEngine | None = None
        self.last_activity = time.monotonic()

        self._inbox: asyncio.Queue[_Inbound] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._presenter: Presenter | None = None
        self._pause_after_trick = (
            ruleset.play.pause_after_trick_seconds
            if pause_after_trick is None
            else pause_after_trick
        )
        self.add_member(host, is_host=True)

    # --- membership --------------------------------------------------------

    @property
    def presenter(self) -> Presenter:
        """Cached: this is read several times per inbound message.

        It only ever changes when somebody takes or leaves a seat, so the two
        places that do that drop the cache.
        """
        if self._presenter is None:
            self._presenter = Presenter(self.seat_names())
        return self._presenter

    def seat_names(self) -> dict[Seat, str]:
        return {
            Seat(member.seat): member.username
            for member in self.members.values()
            if member.seat is not None
        }

    def member_at(self, seat: int) -> Member | None:
        for member in self.members.values():
            if member.seat == seat:
                return member
        return None

    def free_seats(self) -> list[int]:
        taken = {member.seat for member in self.members.values() if member.seat is not None}
        return [seat for seat in range(SEAT_COUNT) if seat not in taken]

    def add_member(self, session: Session, *, is_host: bool = False) -> Member:
        free = self.free_seats()
        seat = free[0] if free else None
        member = Member(session=session, seat=seat, is_host=is_host)
        self.members[session.username] = member
        session.lobby_id = self.id
        session.seat = seat
        self.last_activity = time.monotonic()
        self._presenter = None
        return member

    def remove_member(self, username: str) -> None:
        member = self.members.pop(username, None)
        if member is not None:
            member.session.lobby_id = None
            member.session.seat = None
        self.missing.discard(username)
        self.last_activity = time.monotonic()
        self._presenter = None

    def is_empty(self) -> bool:
        return not self.members

    def has_connected_players(self) -> bool:
        return any(member.connected for member in self.members.values())

    # --- lifecycle ---------------------------------------------------------

    def start_task(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name=f"lobby-{self.id}")

    async def stop_task(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def submit(
        self,
        session: Session,
        message: ClientMessage,
        *,
        correlation: str | None = None,
    ) -> None:
        """Queue a message for this lobby. The only way in."""
        self._inbox.put_nowait(_Inbound(session=session, message=message, correlation=correlation))

    async def _run(self) -> None:
        while True:
            inbound = await self._inbox.get()
            try:
                await self._handle(inbound)
            except IllegalAction as error:
                await self._send(
                    inbound.session,
                    self.presenter.error(ErrorCode.ILLEGAL_MOVE, str(error)),
                    correlation=inbound.correlation,
                )
            except Exception:
                log.exception("lobby %s: onverwachte fout", self.id)
                self.status = LobbyStatusCode.BROKEN
                await self.broadcast(
                    self.presenter.error(ErrorCode.INTERNAL, "Er ging iets mis aan de serverkant.")
                )

    # --- sending -----------------------------------------------------------

    async def _send(
        self, session: Session, message: ServerMessage, *, correlation: str | None = None
    ) -> None:
        agent = session.agent
        if agent is None:
            return
        await agent.deliver(ServerEnvelope(msg=message, re=correlation))

    async def broadcast(self, message: ServerMessage) -> None:
        for member in list(self.members.values()):
            await self._send(member.session, message)

    # --- state views -------------------------------------------------------

    def lobby_state(self) -> LobbyState:
        return LobbyState(
            id=self.id,
            name=self.name,
            host=self.host_username,
            ruleset=self.ruleset_name,
            scoring=self.scoring_name,
            status=self.status,
            members=tuple(
                LobbyMember(
                    username=member.username,
                    seat=member.seat,
                    connected=member.connected,
                    is_host=member.is_host,
                )
                for member in self.members.values()
            ),
        )

    def summary(self) -> LobbySummary:
        return LobbySummary(
            id=self.id,
            name=self.name,
            ruleset=self.ruleset_name,
            scoring=self.scoring_name,
            status=self.status,
            players=len(self.members),
            seats_free=len(self.free_seats()),
        )

    def occupants(self) -> dict[int, Occupant]:
        return {
            member.seat: Occupant(username=member.username, connected=member.connected)
            for member in self.members.values()
            if member.seat is not None
        }

    def snapshot_for(self, session: Session) -> Snapshot:
        """The complete render contract for one player."""
        member = self.members.get(session.username)
        return build_snapshot(
            lobby=self.lobby_state(),
            occupants=self.occupants(),
            engine=self.engine,
            presenter=self.presenter,
            your_seat=member.seat if member else None,
            paused=self.status is LobbyStatusCode.PAUSED,
            missing=self.missing,
        )

    # --- message handling --------------------------------------------------

    async def _handle(self, inbound: _Inbound) -> None:
        message = inbound.message
        session = inbound.session
        self.last_activity = time.monotonic()

        match message:
            case client_messages.ChatSend():
                await self._handle_chat(session, message)
            case client_messages.RequestSnapshot():
                await self._send(
                    session,
                    server_messages.SnapshotMessage(snapshot=self.snapshot_for(session)),
                    correlation=inbound.correlation,
                )
            case client_messages.LobbyStart():
                await self._handle_start(session)
            case client_messages.GameAction():
                await self._handle_game_action(session, message)
            case _:
                await self._send(
                    session,
                    self.presenter.error(
                        ErrorCode.BAD_MESSAGE, "Onbegrijpelijk bericht ontvangen."
                    ),
                    correlation=inbound.correlation,
                )

    async def _handle_chat(self, session: Session, message: client_messages.ChatSend) -> None:
        text = message.text.strip()
        if is_command(text):
            replies = handle_chat_command(
                text,
                ChatContext(lobby=self, session=session),
            )
            for reply in replies:
                await self._send(
                    session,
                    server_messages.Chat(kind=ChatKind.SERVER, text=reply, private=True),
                )
            return

        await self.broadcast(
            server_messages.Chat(kind=ChatKind.PLAYER, text=text, sender=session.username)
        )

    async def _handle_start(self, session: Session) -> None:
        if session.username != self.host_username:
            await self._send(
                session,
                self.presenter.error(
                    ErrorCode.NOT_HOST, "Alleen wie de lobby aanmaakte kan dat doen."
                ),
            )
            return
        if len(self.members) < SEAT_COUNT:
            await self._send(
                session,
                self.presenter.error(
                    ErrorCode.GAME_NOT_RUNNING,
                    f"Wachten op spelers: er zijn er nog {SEAT_COUNT - len(self.members)} nodig.",
                ),
            )
            return
        await self.start_game()

    async def start_game(self) -> None:
        """Begin play. Called once all four seats are filled."""
        if self.engine is not None:
            return
        rng = random.Random(self.rng_seed) if self.rng_seed is not None else random.Random()
        self.engine = GameEngine(self.ruleset, self.scoring, rng=rng)
        self.status = LobbyStatusCode.RUNNING

        await self.broadcast(self.presenter.chat("Iedereen zit klaar. Het spel begint!"))
        for member in self.members.values():
            if member.seat is None:
                continue
            await self._send(
                member.session,
                server_messages.GameStarted(
                    lobby_id=self.id,
                    seats=seat_infos(self.occupants(), self.engine),
                    your_seat=member.seat,
                ),
            )

        events = self.engine.start_round()
        await self._dispatch(events)

    async def _handle_game_action(
        self, session: Session, message: client_messages.GameAction
    ) -> None:
        engine = self.engine
        if engine is None:
            await self._send(
                session,
                self.presenter.error(
                    ErrorCode.GAME_NOT_RUNNING, "Er is op dit moment geen spel bezig."
                ),
            )
            return

        if self.status is LobbyStatusCode.PAUSED:
            await self._send(
                session,
                self.presenter.error(
                    ErrorCode.GAME_PAUSED,
                    f"Het spel is gepauzeerd; we wachten op {', '.join(sorted(self.missing))}.",
                ),
            )
            return

        member = self.members.get(session.username)
        if member is None or member.seat is None:
            await self._send(
                session,
                self.presenter.error(ErrorCode.NOT_IN_LOBBY, "Je zit niet in een lobby."),
            )
            return

        events = engine.apply(Seat(member.seat), message.to_action())
        await self._dispatch(events)

    # --- driving the engine ------------------------------------------------

    async def _dispatch(self, events: list[Event]) -> None:
        """Announce what happened, then re-sync every seat.

        The snapshot is the only thing a client folds into its state, so it goes
        out after every batch of events - including the empty batch. The one
        thing it cannot express is the pause between winning a trick and
        sweeping it: for that moment the table holds four cards the engine has
        already collected, which is why ``table_cleared`` is sent before the
        snapshot that shows an empty table.
        """
        presenter = self.presenter

        for event in events:
            for message in presenter.messages_for(event):
                await self.broadcast(message)

            if isinstance(event, TrickCompleted):
                # The engine has no timers; the delay lives here.
                if self._pause_after_trick:
                    await asyncio.sleep(self._pause_after_trick)
                await self.broadcast(server_messages.TableCleared())

        await self.broadcast_snapshots()
        await self._announce_pending()

    async def broadcast_snapshots(self) -> None:
        """Send every member their own snapshot. Each one carries a private hand."""
        for member in list(self.members.values()):
            await self._send(
                member.session,
                server_messages.SnapshotMessage(snapshot=self.snapshot_for(member.session)),
            )

    async def _announce_pending(self) -> None:
        """Say out loud what the table is waiting for. Safe to call repeatedly.

        Whose turn it is, and with which options, is already in every snapshot;
        this only adds the two requests that the whole table hears - shuffling
        and cutting - and rolls into the next round when one has finished.
        """
        engine = self.engine
        if engine is None or self.status is not LobbyStatusCode.RUNNING:
            return
        prompt = engine.pending()
        if prompt is None:
            if engine.phase is Phase.ROUND_FINISHED:
                events = engine.start_round()
                await self._dispatch(events)
            return

        member = self.member_at(int(prompt.seat))
        if member is None:
            return
        if prompt.kind is PromptKind.CUT:
            await self.broadcast(
                self.presenter.chat(
                    f"{member.username} mag couperen: neem tussen "
                    f"{prompt.cut_minimum} en {prompt.cut_maximum} kaarten af."
                )
            )
        elif prompt.kind is PromptKind.SHUFFLE:
            await self.broadcast(
                self.presenter.chat(f"{member.username}, wil je de kaarten schudden?")
            )

    # --- disconnect / reconnect -------------------------------------------

    async def on_disconnected(self, session: Session) -> None:
        """A player's socket dropped. Pause rather than crash."""
        member = self.members.get(session.username)
        if member is None:
            return
        await self.broadcast(
            server_messages.PlayerDisconnected(username=session.username, seat=member.seat)
        )

        if self.engine is None or self.status not in (
            LobbyStatusCode.RUNNING,
            LobbyStatusCode.PAUSED,
        ):
            return

        # The engine is deliberately not touched: pending() still points at
        # whoever must act, so resuming is just re-issuing the prompt.
        self.missing.add(session.username)
        self.status = LobbyStatusCode.PAUSED
        text = f"{session.username} is de verbinding kwijt. Het spel pauzeert tot hij terug is."
        await self.broadcast(
            server_messages.GamePaused(missing=tuple(sorted(self.missing)), text=text)
        )
        await self.broadcast(self.presenter.chat(text))
        await self.broadcast_snapshots()

    async def on_reconnected(self, session: Session) -> None:
        """A player came back. Resync them fully, then resume if all are present."""
        member = self.members.get(session.username)
        if member is None:
            return

        await self._send(session, server_messages.LobbyStateMessage(lobby=self.lobby_state()))
        await self._send(
            session, server_messages.SnapshotMessage(snapshot=self.snapshot_for(session))
        )
        await self.broadcast(
            server_messages.PlayerReconnected(username=session.username, seat=member.seat)
        )

        self.missing.discard(session.username)
        if self.missing or self.status is not LobbyStatusCode.PAUSED:
            return

        self.status = LobbyStatusCode.RUNNING
        text = f"{session.username} is terug. Het spel gaat verder."
        await self.broadcast(server_messages.GameResumed(text=text))
        await self.broadcast(self.presenter.chat(text))
        # Idempotent: the engine never recorded that it already asked, so the
        # pending turn simply reappears in the snapshot everyone now gets.
        await self.broadcast_snapshots()
        await self._announce_pending()
