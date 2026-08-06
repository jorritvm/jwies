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
    GameFinished,
    IllegalAction,
    TrickCompleted,
)
from jwies_core.seats import ALL_SEATS, Seat
from jwies_server import protocol
from jwies_server.chat import ChatContext, handle_chat_command, is_command
from jwies_server.presenter import Presenter
from jwies_server.protocol import ErrorCode, LobbyStatusCode
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
    message: protocol.ClientMessage


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

    async def send_table(self, session: Session) -> None:
        """Seat one member at the table and hand them their cards.

        What ``start_game`` does for everybody at once, for a single player who
        arrived after the deal - taking over a seat somebody vacated. Without
        this their client sits on the lobby page with a running game behind it,
        because ``game_started`` and the first snapshot have long since gone.
        """
        member = self.members.get(session.username)
        if self.engine is None or member is None or member.seat is None:
            return
        await self._send(
            session,
            protocol.GameStarted(
                seats=seat_infos(self.occupants(), self.engine), your_seat=member.seat
            ),
        )
        await self._send(
            session, protocol.SnapshotMessage(snapshot=self.snapshot_for(session))
        )

    async def resume_if_nobody_is_missing(self) -> None:
        """Unpause once the table is complete again.

        Somebody who drops out and then leaves for good takes their name off the
        missing list without ever coming back, which would otherwise leave the
        other three paused on nobody at all.
        """
        if self.status is not LobbyStatusCode.PAUSED or self.missing:
            return
        self.status = LobbyStatusCode.RUNNING
        await self.broadcast(protocol.GameResumed(text="Het spel gaat verder."))
        await self.broadcast(self.presenter.chat("Het spel gaat verder."))
        await self.broadcast_snapshots()
        await self._announce_pending()

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

    def submit(self, session: Session, message: protocol.ClientMessage) -> None:
        """Queue a message for this lobby. The only way in."""
        self._inbox.put_nowait(_Inbound(session=session, message=message))

    async def _run(self) -> None:
        while True:
            inbound = await self._inbox.get()
            try:
                await self._handle(inbound)
            except IllegalAction as error:
                await self._send(
                    inbound.session,
                    self.presenter.error(ErrorCode.ILLEGAL_MOVE, str(error)),
                )
            except Exception:
                log.exception("lobby %s: onverwachte fout", self.id)
                self.status = LobbyStatusCode.BROKEN
                await self.broadcast(
                    self.presenter.error(ErrorCode.INTERNAL, "Er ging iets mis aan de serverkant.")
                )

    # --- sending -----------------------------------------------------------

    async def _send(self, session: Session, message: protocol.ServerMessage) -> None:
        agent = session.agent
        if agent is None:
            return
        await agent.deliver(protocol.ServerEnvelope(msg=message))

    async def broadcast(self, message: protocol.ServerMessage) -> None:
        for member in list(self.members.values()):
            await self._send(member.session, message)

    # --- state views -------------------------------------------------------

    def lobby_state(self) -> protocol.LobbyState:
        return protocol.LobbyState(
            id=self.id,
            name=self.name,
            host=self.host_username,
            ruleset=self.ruleset_name,
            scoring=self.scoring_name,
            status=self.status,
            members=tuple(
                protocol.LobbyMember(
                    username=member.username,
                    seat=member.seat,
                    connected=member.connected,
                    is_host=member.is_host,
                )
                for member in self.members.values()
            ),
        )

    def summary(self) -> protocol.LobbySummary:
        return protocol.LobbySummary(
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

    def snapshot_for(self, session: Session) -> protocol.Snapshot:
        """The complete render contract for one player."""
        member = self.members.get(session.username)
        return build_snapshot(
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
            case protocol.ChatSend():
                await self._handle_chat(session, message)
            case protocol.RequestSnapshot():
                await self._send(
                    session,
                    protocol.SnapshotMessage(snapshot=self.snapshot_for(session)),
                )
            case protocol.GameAction():
                await self._handle_game_action(session, message)
            case _:
                await self._send(
                    session,
                    self.presenter.error(
                        ErrorCode.BAD_MESSAGE, "Onbegrijpelijk bericht ontvangen."
                    ),
                )

    async def _handle_chat(self, session: Session, message: protocol.ChatSend) -> None:
        text = message.text.strip()
        # A command is an ordinary line in the channel first: the table sees who
        # asked, the way it did on IRC.
        await self.broadcast(
            protocol.Chat(kind=protocol.ChatKind.PLAYER, text=text, sender=session.username)
        )
        if not is_command(text):
            return

        # And the answer is spoken out loud too. Answered privately it left the
        # rest of the table looking at a question with no reply, and anyone who
        # wanted the same thing had to ask for it again himself.
        replies = handle_chat_command(text, ChatContext(lobby=self, session=session))
        for reply in replies:
            await self.broadcast(protocol.Chat(kind=protocol.ChatKind.SERVER, text=reply))

    async def start_game(self) -> None:
        """Begin play. Called once all four seats are filled.

        There is no host-initiated start: the table fills up and the game
        begins, which is what ``LobbyManager.is_startable`` decides.
        """
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
                protocol.GameStarted(
                    seats=seat_infos(self.occupants(), self.engine),
                    your_seat=member.seat,
                ),
            )

        events = self.engine.start_round()
        await self._dispatch(events)

    async def _handle_game_action(
        self, session: Session, message: protocol.GameAction
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

            if isinstance(event, GameFinished):
                # The last round of a bounded game has been scored. Without
                # this the lobby stays RUNNING and the list keeps advertising a
                # table that will never ask anyone for anything again.
                self.status = LobbyStatusCode.FINISHED

            if isinstance(event, TrickCompleted):
                # The engine has no timers; the delay lives here.
                if self._pause_after_trick:
                    await asyncio.sleep(self._pause_after_trick)
                await self.broadcast(protocol.TableCleared())

        await self.broadcast_snapshots()
        await self._announce_pending()

    async def broadcast_snapshots(self) -> None:
        """Send every member their own snapshot. Each one carries a private hand."""
        for member in list(self.members.values()):
            await self._send(
                member.session,
                protocol.SnapshotMessage(snapshot=self.snapshot_for(member.session)),
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
            protocol.PlayerDisconnected(username=session.username, seat=member.seat)
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
            protocol.GamePaused(missing=tuple(sorted(self.missing)), text=text)
        )
        await self.broadcast(self.presenter.chat(text))
        await self.broadcast_snapshots()

    async def on_reconnected(self, session: Session) -> None:
        """A player came back. Resync them fully, then resume if all are present."""
        member = self.members.get(session.username)
        if member is None:
            return

        await self._send(session, protocol.LobbyStateMessage(lobby=self.lobby_state()))
        await self._send(
            session, protocol.SnapshotMessage(snapshot=self.snapshot_for(session))
        )
        await self.broadcast(
            protocol.PlayerReconnected(username=session.username, seat=member.seat)
        )

        self.missing.discard(session.username)
        if self.missing or self.status is not LobbyStatusCode.PAUSED:
            return

        self.status = LobbyStatusCode.RUNNING
        text = f"{session.username} is terug. Het spel gaat verder."
        await self.broadcast(protocol.GameResumed(text=text))
        await self.broadcast(self.presenter.chat(text))
        # Idempotent: the engine never recorded that it already asked, so the
        # pending turn simply reappears in the snapshot everyone now gets.
        await self.broadcast_snapshots()
        await self._announce_pending()
