"""Building the per-seat snapshot.

The snapshot is the only thing a client folds into its state, so this is where
the whole render contract is filled in. It lives outside ``LobbyRuntime``:
given a table's occupants, its engine and a presenter, the result is a pure
function of the arguments, which is what makes it testable in three lines.

Built per recipient and never broadcast: it carries that player's hand.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from jwies_core.cards import Suit
from jwies_core.engine import GameEngine, Phase
from jwies_core.seats import ALL_SEATS, Seat
from jwies_core.trick import PlayedCard
from jwies_server.presenter import Presenter, _decimal
from jwies_server.protocol import (
    BidRecord,
    PhaseCode,
    PlayedCardInfo,
    SeatInfo,
    Snapshot,
    TrickCounts,
)

__all__ = ["Occupant", "build_snapshot", "seat_infos"]


@dataclass(frozen=True, slots=True)
class Occupant:
    """Who is sitting in a seat, as far as a snapshot cares."""

    username: str
    connected: bool


def build_snapshot(
    *,
    occupants: Mapping[int, Occupant],
    engine: GameEngine | None,
    presenter: Presenter,
    your_seat: int | None,
    paused: bool,
    missing: Collection[str],
) -> Snapshot:
    """Everything the player in ``your_seat`` may know about this table."""
    if engine is None:
        return Snapshot(
            phase=PhaseCode.WAITING_FOR_SHUFFLE,
            your_seat=your_seat,
            seats=seat_infos(occupants, None),
            paused=paused,
            missing_players=tuple(sorted(missing)),
        )

    pending = engine.pending()
    on_turn = pending is not None and your_seat is not None and int(pending.seat) == your_seat
    contract = engine.round.contract
    trump = engine.round.trump

    return Snapshot(
        phase=engine.phase,
        round_number=engine.round_number,
        multiplier=_decimal(engine.round.multiplier),
        your_seat=your_seat,
        dealer_seat=int(engine.round.dealer),
        seats=seat_infos(occupants, engine),
        your_hand=(
            tuple(card.code for card in engine.hand_of(Seat(your_seat)))
            if your_seat is not None
            else ()
        ),
        # Only misere ouverte puts anyone else's cards on the table.
        open_hands={
            int(seat): tuple(card.code for card in cards)
            for seat, cards in engine.open_hands().items()
        },
        turned_trump=(
            engine.round.turned_trump.code
            if engine.round.turned_trump is not None and engine.phase is Phase.BIDDING
            else None
        ),
        trump=trump if isinstance(trump, Suit) else None,
        bids=tuple(
            BidRecord(
                seat=int(entry.seat),
                bid=presenter.bid_info(entry.bid),
                announcement=presenter.bid_announcement(entry.seat, entry.bid),
            )
            for entry in engine.round.bids
        ),
        contract=presenter.contract_info(contract) if contract else None,
        current_trick=_played(engine.round.trick),
        last_trick=_played(engine.round.last_trick) or None,
        trick_counts=TrickCounts(
            declarers=engine.round.declarer_tricks,
            defenders=engine.round.defender_tricks,
        ),
        totals={occupant.username: _total(engine, seat) for seat, occupant in occupants.items()},
        pending_seat=int(pending.seat) if pending else None,
        # The legal moves travel with the turn, so no client ever has to derive
        # follow-suit or the bidding ladder - and only the player on turn is
        # told what they are.
        prompt=presenter.prompt(pending) if on_turn and pending else None,
        paused=paused,
        missing_players=tuple(sorted(missing)),
        # Only the declaring side can give up, so the offer is addressed to you
        # personally. The tally is not private: everyone sees who has agreed.
        folding_offered=(
            engine.folding_is_offered() and contract is not None and your_seat in contract.declarers
        ),
        payout_settled=engine.payout_is_settled(),
        folded=tuple(sorted(int(seat) for seat in engine.round.folded)),
    )


def seat_infos(
    occupants: Mapping[int, Occupant], engine: GameEngine | None
) -> tuple[SeatInfo, ...]:
    """One row per seat, occupied or not. Also what ``game_started`` carries."""
    return tuple(
        SeatInfo(
            seat=int(seat),
            username=occupants[int(seat)].username if int(seat) in occupants else None,
            connected=int(seat) in occupants and occupants[int(seat)].connected,
            is_dealer=bool(engine and engine.round.dealer == seat),
        )
        for seat in ALL_SEATS
    )


def _played(cards: Iterable[PlayedCard]) -> tuple[PlayedCardInfo, ...]:
    return tuple(PlayedCardInfo(seat=int(entry.seat), card=entry.card.code) for entry in cards)


def _total(engine: GameEngine | None, seat: int) -> str:
    if engine is None:
        return "0"
    return _decimal(engine.totals.get(Seat(seat), Decimal(0)))
