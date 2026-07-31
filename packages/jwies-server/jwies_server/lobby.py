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
from decimal import Decimal

from jwies_core.bidding import Bid, BidType
from jwies_core.cards import Card, Suit
from jwies_core.config import Ruleset, ScoringScale
from jwies_core.engine import GameEngine, Phase, PromptKind
from jwies_core.events import (
    CardsDealt,
    Cut,
    Event,
    IllegalAction,
    PlaceBid,
    PlayCard,
    Shuffle,
    TrickCompleted,
)
from jwies_core.seats import ALL_SEATS, Seat
from jwies_protocol import (
    ChatKind,
    ClientMessage,
    ErrorCode,
    LobbyMember,
    LobbyState,
    LobbyStatusCode,
    LobbySummary,
    PhaseCode,
    PlayedCardInfo,
    SeatInfo,
    ServerEnvelope,
    ServerMessage,
    Snapshot,
    TrickCounts,
    client_messages,
    server_messages,
)

from jwies_server.agents import PlayerAgent
from jwies_server.chat import ChatContext, handle_chat_command, is_command
from jwies_server.presenter import Presenter, _decimal
from jwies_server.sessions import Session
from jwies_server.texts import TextCatalog

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
    agent: PlayerAgent | None
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
        catalog: TextCatalog,
        rng_seed: int | None = None,
        pause_after_trick: float | None = None,
    ) -> None:
        self.id = lobby_id
        self.name = name
        self.ruleset = ruleset
        self.ruleset_name = ruleset_name
        self.scoring = scoring
        self.scoring_name = scoring_name
        self.catalog = catalog
        self.rng_seed = rng_seed
        self.status = LobbyStatusCode.WAITING

        self.members: dict[str, Member] = {}
        self.host_username = host.username
        self.missing: set[str] = set()
        self.engine: GameEngine | None = None
        self.last_activity = time.monotonic()

        self._inbox: asyncio.Queue[_Inbound] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._pause_after_trick = (
            ruleset.play.pause_after_trick_seconds
            if pause_after_trick is None
            else pause_after_trick
        )
        self.add_member(host, is_host=True)

    # --- membership --------------------------------------------------------

    @property
    def presenter(self) -> Presenter:
        return Presenter(self.catalog, self.seat_names())

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
        return member

    def remove_member(self, username: str) -> None:
        member = self.members.pop(username, None)
        if member is not None:
            member.session.lobby_id = None
            member.session.seat = None
        self.missing.discard(username)
        self.last_activity = time.monotonic()

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
        self._inbox.put_nowait(
            _Inbound(
                agent=session.agent,
                session=session,
                message=message,
                correlation=correlation,
            )
        )

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
                    self.presenter.error(ErrorCode.INTERNAL, self.catalog.render("error.internal"))
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

    async def broadcast_all(self, messages: list[ServerMessage]) -> None:
        for message in messages:
            await self.broadcast(message)

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

    def snapshot_for(self, session: Session) -> Snapshot:
        """The complete render contract for one player.

        Built per recipient, never broadcast: it carries that player's hand.
        """
        member = self.members.get(session.username)
        seat = member.seat if member else None
        engine = self.engine
        presenter = self.presenter

        if engine is None:
            return Snapshot(
                lobby=self.lobby_state(),
                phase=PhaseCode.WAITING_FOR_SHUFFLE,
                your_seat=seat,
                seats=self._seat_infos(),
                paused=self.status is LobbyStatusCode.PAUSED,
                missing_players=tuple(sorted(self.missing)),
            )

        contract = engine.round.contract
        prompt = engine.pending()
        your_prompt = None
        if prompt is not None and seat is not None and int(prompt.seat) == seat:
            your_prompt = presenter.prompt(prompt)

        trump = engine.round.trump
        return Snapshot(
            lobby=self.lobby_state(),
            phase=PhaseCode(engine.phase.value),
            round_number=engine.round_number,
            multiplier=_decimal(engine.round.multiplier),
            your_seat=seat,
            dealer_seat=int(engine.round.dealer),
            seats=self._seat_infos(),
            your_hand=(
                tuple(card.code for card in engine.hand_of(Seat(seat))) if seat is not None else ()
            ),
            open_hands={
                int(open_seat): tuple(card.code for card in cards)
                for open_seat, cards in engine.open_hands().items()
            },
            turned_trump=(
                engine.round.turned_trump.code
                if engine.round.turned_trump is not None and engine.phase is Phase.BIDDING
                else None
            ),
            trump=trump.value if isinstance(trump, Suit) else None,  # type: ignore[arg-type]
            bids=tuple(
                {  # type: ignore[misc]
                    "seat": int(entry.seat),
                    "bid": presenter.bid_info(entry.bid),
                    "forced": entry.forced,
                    "announcement": presenter.bid_announcement(entry.seat, entry.bid),
                }
                for entry in engine.round.bids
            ),
            contract=presenter.contract_info(contract) if contract else None,
            current_trick=tuple(
                PlayedCardInfo(seat=int(played.seat), card=played.card.code)
                for played in engine.round.trick
            ),
            last_trick=(
                tuple(
                    PlayedCardInfo(seat=int(played.seat), card=played.card.code)
                    for played in engine.round.last_trick
                )
                or None
            ),
            trick_counts=TrickCounts(
                declarers=engine.round.declarer_tricks,
                defenders=engine.round.defender_tricks,
            ),
            totals={
                member.username: _decimal(engine.totals.get(Seat(member.seat), Decimal(0)))
                for member in self.members.values()
                if member.seat is not None
            },
            pending_seat=int(prompt.seat) if prompt else None,
            prompt=your_prompt,
            paused=self.status is LobbyStatusCode.PAUSED,
            missing_players=tuple(sorted(self.missing)),
        )

    def _seat_infos(self) -> tuple[SeatInfo, ...]:
        engine = self.engine
        contract = engine.round.contract if engine else None
        infos = []
        for seat in range(SEAT_COUNT):
            member = self.member_at(seat)
            infos.append(
                SeatInfo(
                    seat=seat,
                    username=member.username if member else None,
                    connected=member.connected if member else False,
                    is_dealer=bool(engine and int(engine.round.dealer) == seat),
                    is_declarer=bool(contract and seat in contract.declarers),
                    total=_decimal(engine.totals.get(Seat(seat), Decimal(0))) if engine else "0",
                )
            )
        return tuple(infos)

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
            case (
                client_messages.AnswerShuffle()
                | client_messages.AnswerCut()
                | client_messages.PlaceBid()
                | client_messages.PlayCard()
            ):
                await self._handle_game_action(session, message)
            case _:
                await self._send(
                    session,
                    self.presenter.error(
                        ErrorCode.BAD_MESSAGE, self.catalog.render("error.bad_message")
                    ),
                    correlation=inbound.correlation,
                )

    async def _handle_chat(self, session: Session, message: client_messages.ChatSend) -> None:
        text = message.text.strip()
        if is_command(text):
            replies = handle_chat_command(
                text,
                ChatContext(lobby=self, session=session, catalog=self.catalog),
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
                self.presenter.error(ErrorCode.NOT_HOST, self.catalog.render("error.not_host")),
            )
            return
        if len(self.members) < SEAT_COUNT:
            await self._send(
                session,
                self.presenter.error(
                    ErrorCode.GAME_NOT_RUNNING,
                    self.catalog.render(
                        "lobby.waiting_for_players",
                        aantal=SEAT_COUNT - len(self.members),
                    ),
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

        await self.broadcast(self.presenter.chat(self.catalog.render("lobby.game_starts")))
        for member in self.members.values():
            if member.seat is None:
                continue
            await self._send(
                member.session,
                server_messages.GameStarted(
                    lobby_id=self.id,
                    seats=self._seat_infos(),
                    your_seat=member.seat,
                ),
            )

        events = self.engine.start_round()
        await self._dispatch(events)

    async def _handle_game_action(self, session: Session, message: ClientMessage) -> None:
        engine = self.engine
        if engine is None:
            await self._send(
                session,
                self.presenter.error(
                    ErrorCode.GAME_NOT_RUNNING,
                    self.catalog.render("error.game_not_running"),
                ),
            )
            return

        if self.status is LobbyStatusCode.PAUSED:
            await self._send(
                session,
                self.presenter.error(
                    ErrorCode.GAME_PAUSED,
                    self.catalog.render(
                        "error.game_paused", spelers=", ".join(sorted(self.missing))
                    ),
                ),
            )
            return

        member = self.members.get(session.username)
        if member is None or member.seat is None:
            await self._send(
                session,
                self.presenter.error(
                    ErrorCode.NOT_IN_LOBBY, self.catalog.render("error.not_in_lobby")
                ),
            )
            return

        seat = Seat(member.seat)
        action = self._to_action(message)
        events = engine.apply(seat, action)
        await self._dispatch(events)

    @staticmethod
    def _to_action(message: ClientMessage) -> Shuffle | Cut | PlaceBid | PlayCard:
        match message:
            case client_messages.AnswerShuffle():
                return Shuffle(shuffle=message.shuffle)
            case client_messages.AnswerCut():
                return Cut(count=message.count)
            case client_messages.PlaceBid():
                return PlaceBid(
                    bid=Bid(
                        type=BidType(message.bid.type.value),
                        tricks=message.bid.tricks,
                        suit=Suit(message.bid.suit.value) if message.bid.suit else None,
                    )
                )
            case client_messages.PlayCard():
                return PlayCard(card=Card.from_code(message.card))
        raise IllegalAction("onbekende actie")

    # --- driving the engine ------------------------------------------------

    async def _dispatch(self, events: list[Event]) -> None:
        """Broadcast the events, deal private information, then re-prompt."""
        presenter = self.presenter

        for event in events:
            # Hands are private, so they are sent per seat and only when cards
            # are actually dealt. Clients track their own hand from there; a
            # reconnecting player gets it back through the snapshot instead.
            if isinstance(event, CardsDealt):
                await self._deal_private_hands()

            for message in presenter.messages_for(event):
                await self.broadcast(message)

            if isinstance(event, TrickCompleted):
                # The trick stays on the table for a moment before it is swept.
                # The engine has no timers; the delay lives here.
                if self._pause_after_trick:
                    await asyncio.sleep(self._pause_after_trick)
                await self.broadcast(server_messages.TableCleared())

        await self._issue_prompt()

    async def _deal_private_hands(self) -> None:
        engine = self.engine
        if engine is None:
            return
        for member in self.members.values():
            if member.seat is None:
                continue
            hand = engine.hand_of(Seat(member.seat))
            if hand:
                await self._send(
                    member.session,
                    server_messages.HandDealt(cards=tuple(card.code for card in hand)),
                )

    async def _issue_prompt(self) -> None:
        """Ask whoever is due to act. Safe to call repeatedly."""
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
        await self._send(
            member.session,
            server_messages.PromptMessage(prompt=self.presenter.prompt(prompt)),
        )
        if prompt.kind is PromptKind.CUT:
            await self.broadcast(
                self.presenter.chat(
                    self.catalog.render(
                        "game.cut_request",
                        speler=member.username,
                        min=prompt.cut_minimum,
                        max=prompt.cut_maximum,
                    )
                )
            )
        elif prompt.kind is PromptKind.SHUFFLE:
            await self.broadcast(
                self.presenter.chat(
                    self.catalog.render("game.shuffle_request", speler=member.username)
                )
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
        text = self.catalog.render("pause.player_gone", speler=session.username)
        await self.broadcast(
            server_messages.GamePaused(missing=tuple(sorted(self.missing)), text=text)
        )
        await self.broadcast(self.presenter.chat(text))

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
        text = self.catalog.render("pause.resumed", speler=session.username)
        await self.broadcast(server_messages.GameResumed(text=text))
        await self.broadcast(self.presenter.chat(text))
        # Idempotent: the engine never recorded that it already asked.
        await self._issue_prompt()
