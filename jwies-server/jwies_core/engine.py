"""The game state machine.

Pure and synchronous. State changes are returned as a list of events rather
than performed as side effects, and timing (like the pause after a full
trick) is the server's business, not the engine's.

Two properties are load-bearing beyond mere tidiness:

* ``pending()`` is idempotent and re-issuable. The engine never records "I
  already asked seat 2 to play", so re-sending a prompt after a reconnect is
  free - that is what makes pause/resume trivial.
* ``rng`` is injected, so a seeded game replays identically. Tests and a future
  AI both depend on it.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from jwies_core.bidding import Bid, BidEntry, BidLadder, BidType
from jwies_core.cards import (
    CARDS_PER_HAND,
    DECK_SIZE,
    Card,
    Suit,
    shuffled_deck,
    sort_for_hand,
)
from jwies_core.config.ruleset import AllPassedRule, Ruleset
from jwies_core.config.scoring_scale import ScoringScale
from jwies_core.contracts import Contract, ContractKey
from jwies_core.events import (
    Action,
    BiddingFinished,
    BidPlaced,
    CardPlayed,
    CardsDealt,
    ContractEstablished,
    ContractLost,
    Cut,
    DealerAnnounced,
    DeckCut,
    Event,
    Fold,
    FoldingChanged,
    GameFinished,
    IllegalAction,
    PlaceBid,
    PlayCard,
    RedealRequired,
    RoundScored,
    Shuffle,
    TrickCompleted,
    TrumpTurned,
)
from jwies_core.resolution import RedealReason, resolve_contract
from jwies_core.scoring import RoundResult, payout_is_settled, score_round
from jwies_core.seats import (
    ALL_SEATS,
    FIRST_SEAT,
    Seat,
    left_of,
    right_of,
    seat_order_from,
)
from jwies_core.trick import PlayedCard, legal_moves, trick_winner
from jwies_core.troel import TroelResult, detect_troel

__all__ = ["GameEngine", "Phase", "Prompt", "PromptKind"]


class Phase(StrEnum):
    WAITING_FOR_SHUFFLE = "waiting_for_shuffle"
    WAITING_FOR_CUT = "waiting_for_cut"
    BIDDING = "bidding"
    PLAYING = "playing"
    ROUND_FINISHED = "round_finished"
    GAME_FINISHED = "game_finished"


class PromptKind(StrEnum):
    SHUFFLE = "shuffle"
    CUT = "cut"
    BID = "bid"
    PLAY = "play"


@dataclass(frozen=True, slots=True)
class Prompt:
    """What the engine is waiting for, and the options available.

    The legal option set travels with the prompt so no client ever has to
    re-derive follow-suit or the bidding ladder.
    """

    seat: Seat
    kind: PromptKind
    bid_options: tuple[Bid, ...] = ()
    legal_cards: tuple[Card, ...] = ()
    cut_minimum: int = 0
    cut_maximum: int = 0


_PROMPT_FOR_ACTION: dict[type, PromptKind] = {
    Shuffle: PromptKind.SHUFFLE,
    Cut: PromptKind.CUT,
    PlaceBid: PromptKind.BID,
    PlayCard: PromptKind.PLAY,
}

_WHAT_IS_ASKED: dict[PromptKind, str] = {
    PromptKind.SHUFFLE: "een antwoord over het schudden",
    PromptKind.CUT: "een aantal kaarten om af te nemen",
    PromptKind.BID: "een bod",
    PromptKind.PLAY: "een kaart",
}


@dataclass
class _RoundState:
    """Everything that resets between rounds."""

    dealer: Seat
    multiplier: Decimal = Decimal(1)
    hands: dict[Seat, list[Card]] = field(default_factory=dict)
    turned_trump: Card | None = None
    bids: list[BidEntry] = field(default_factory=list)
    seat_to_bid: Seat = FIRST_SEAT
    troel: TroelResult | None = None
    contract: Contract | None = None
    trump: Suit | None = None
    trick: list[PlayedCard] = field(default_factory=list)
    last_trick: tuple[PlayedCard, ...] = ()
    # Won tricks are kept per side because traditional wiezen does not reshuffle
    # between rounds: the cards are gathered up in the order they were won.
    declarer_won: list[tuple[Card, ...]] = field(default_factory=list)
    defender_won: list[tuple[Card, ...]] = field(default_factory=list)
    tricks_played: int = 0
    to_play: Seat | None = None
    # Seats willing to stop this round early. Cleared with the round.
    folded: set[Seat] = field(default_factory=set)
    contract_lost_announced: bool = False

    @property
    def declarer_tricks(self) -> int:
        return len(self.declarer_won)

    @property
    def defender_tricks(self) -> int:
        return len(self.defender_won)


class GameEngine:
    """A single game of Vlaamse wies at one table."""

    def __init__(
        self,
        ruleset: Ruleset,
        scale: ScoringScale,
        *,
        rng: random.Random | None = None,
        dealer: Seat = Seat(0),
    ) -> None:
        self.ruleset = ruleset
        self.scale = scale
        self.rng = rng or random.Random()
        self.ladder = BidLadder(ruleset)

        self.round_number = 0
        self.totals: dict[Seat, Decimal] = {seat: Decimal(0) for seat in ALL_SEATS}
        self.phase = Phase.WAITING_FOR_SHUFFLE
        self._deck: list[Card] = shuffled_deck(self.rng)
        # The opening deck comes out of the box shuffled, so the first deal is
        # cut. After that the cut only follows a shuffle - see _cut_or_deal.
        self._deck_is_shuffled = True
        self._next_multiplier = Decimal(1)
        self.round = _RoundState(dealer=dealer)
        self._started = False

    # --- lifecycle --------------------------------------------------------

    def start_round(self) -> list[Event]:
        """Begin a new round. Call once at game start, then after each round."""
        if self.phase is Phase.GAME_FINISHED:
            raise IllegalAction("het spel is afgelopen")

        if self._started:
            self.round = _RoundState(dealer=left_of(self.round.dealer))
        self._started = True

        self.round_number += 1
        self.round.multiplier = self._next_multiplier
        self._next_multiplier = Decimal(1)
        self.round.seat_to_bid = left_of(self.round.dealer)

        events: list[Event] = [
            DealerAnnounced(
                round_number=self.round_number,
                dealer=self.round.dealer,
                multiplier=self.round.multiplier,
            )
        ]

        if self.ruleset.deal.dealer_may_shuffle:
            self.phase = Phase.WAITING_FOR_SHUFFLE
            return events

        events.extend(self._cut_or_deal())
        return events

    def _redeal(self, reason: RedealReason) -> list[Event]:
        """Collect the cards and deal again, per the ruleset."""
        self._collect_cards()

        if reason is RedealReason.ASK_DECLINED:
            next_dealer = left_of(self.round.dealer)
        else:
            next_dealer = self.round.dealer
            if (
                self.ruleset.bidding.all_passed is AllPassedRule.NEXT_ROUND_DOUBLE
                and self.scale.all_passed_doubles
            ):
                self._next_multiplier = self.round.multiplier * 2

        events: list[Event] = [RedealRequired(reason=reason.value, next_dealer=next_dealer)]
        self.round = _RoundState(dealer=next_dealer)
        self._started = False
        self.round_number -= 1  # the redeal is not a new round
        events.extend(self.start_round())
        return events

    # --- the single source of truth for "whose turn is it" ----------------

    def pending(self) -> Prompt | None:
        """What the engine is waiting for, or ``None`` when nothing is due.

        Safe to call any number of times; re-issuing the result after a
        reconnect is exactly what resuming a paused game needs.
        """
        match self.phase:
            case Phase.WAITING_FOR_SHUFFLE:
                return Prompt(seat=self.round.dealer, kind=PromptKind.SHUFFLE)
            case Phase.WAITING_FOR_CUT:
                return Prompt(
                    seat=right_of(self.round.dealer),
                    kind=PromptKind.CUT,
                    cut_minimum=self.ruleset.deal.cut_minimum,
                    cut_maximum=self.ruleset.deal.cut_maximum,
                )
            case Phase.BIDDING:
                seat = self.round.seat_to_bid
                return Prompt(
                    seat=seat,
                    kind=PromptKind.BID,
                    bid_options=tuple(self.ladder.options_after(self.round.bids, seat)),
                )
            case Phase.PLAYING:
                to_play = self.round.to_play
                if to_play is None:
                    return None
                return Prompt(
                    seat=to_play,
                    kind=PromptKind.PLAY,
                    legal_cards=tuple(self._legal_cards(to_play)),
                )
            case _:
                return None

    def _legal_cards(self, seat: Seat) -> list[Card]:
        contract = self.round.contract
        must_lead_highest_trump = (
            contract is not None
            and contract.key is ContractKey.TROEL
            and self.ruleset.play.troel_must_lead_highest_trump
            and self.ruleset.bidding.troel_tricks == 8
            and self.round.tricks_played == 0
            and not self.round.trick
        )
        return legal_moves(
            sort_for_hand(self.round.hands.get(seat, [])),
            self.round.trick,
            self.round.trump,
            must_lead_highest_trump=must_lead_highest_trump,
        )

    # --- applying actions -------------------------------------------------

    def apply(self, seat: Seat, action: Action) -> list[Event]:
        """Apply one action, returning the events it caused."""
        # Folding is the table deciding something together rather than one
        # player taking his turn, so it is the one action that does not wait
        # for the prompt to come round.
        if isinstance(action, Fold):
            return self._apply_fold(seat, action)

        prompt = self.pending()
        if prompt is None:
            raise IllegalAction("er wordt op dit moment niets van je verwacht")
        if prompt.seat != seat:
            raise IllegalAction("het is niet jouw beurt")

        # Being the right player is not enough: the action has to be the one
        # actually being asked for. A card played a moment too late arrives in
        # the next round, where the same seat may well be the dealer and so pass
        # the check above - and then a play would run against a hand that has
        # not been dealt yet. That is a crash, and a crash takes the table down
        # with it, so it is refused here as an ordinary illegal move.
        expected = _PROMPT_FOR_ACTION.get(type(action))
        if expected is None:
            raise IllegalAction("onbekende actie")
        if prompt.kind is not expected:
            raise IllegalAction(
                f"dat kan nu niet: er wordt {_WHAT_IS_ASKED[prompt.kind]} van je verwacht"
            )

        match action:
            case Shuffle():
                return self._apply_shuffle(action)
            case Cut():
                return self._apply_cut(seat, action)
            case PlaceBid():
                return self._apply_bid(seat, action)
            case PlayCard():
                return self._apply_play(seat, action)
        raise IllegalAction("onbekende actie")

    # --- folding ----------------------------------------------------------

    def tricks_remaining(self) -> int:
        return CARDS_PER_HAND - self.round.tricks_played

    def folding_is_offered(self) -> bool:
        """Whether the declaring side may give up right now.

        Two things must hold: the ruleset allows it, and the contract can no
        longer be made. Giving up concedes every remaining trick to the
        defenders, so the declaring side is choosing its own worst case - the
        defenders cannot come out behind, which is why their consent is not
        asked for. Whether conceding actually costs anything is a separate
        question, and the answer is in ``payout_is_settled``.
        """
        contract = self.round.contract
        if not self.ruleset.play.folding_allowed or contract is None:
            return False
        if self.phase is not Phase.PLAYING:
            return False
        return not contract.can_still_be_made(self.round.declarer_tricks, self.tricks_remaining())

    def payout_is_settled(self) -> bool:
        """Whether giving up now would cost the declaring side nothing.

        True for the solo contracts, which are fined a flat amount, and false
        for the duo contracts, which pay per missing trick. Clients use it to
        warn before conceding tricks that are still worth something.
        """
        contract = self.round.contract
        if contract is None:
            return False
        return payout_is_settled(
            contract,
            self.round.declarer_tricks,
            self.tricks_remaining(),
            self.scale,
            self.round.multiplier,
        )

    def _apply_fold(self, seat: Seat, action: Fold) -> list[Event]:
        if not self.folding_is_offered():
            raise IllegalAction("er valt op dit moment niets op te geven")
        contract = self.round.contract
        assert contract is not None  # folding_is_offered checked it
        if seat not in contract.declarers:
            raise IllegalAction("enkel de spelende partij kan opgeven")

        before = set(self.round.folded)
        if action.fold:
            self.round.folded.add(seat)
        else:
            self.round.folded.discard(seat)
        if self.round.folded == before:
            return []

        events: list[Event] = [FoldingChanged(folded=frozenset(self.round.folded))]
        if not self.round.folded.issuperset(contract.declarers):
            # A partner still has to agree: conceding costs him points too.
            return events

        # The declaring side gave up. Every remaining trick goes to the
        # defenders, which is exactly the score as it already stands, so the
        # cards are simply gathered up as they lie.
        return events + self._score_round(folded=True)

    def _apply_shuffle(self, action: Shuffle) -> list[Event]:
        if action.shuffle:
            self.rng.shuffle(self._deck)
            self._deck_is_shuffled = True
        return self._cut_or_deal()

    def _cut_or_deal(self) -> list[Event]:
        """Offer the cut, but only on a deck that has been shuffled.

        Cutting is what protects the table against a shuffle nobody saw. A pack
        that was not shuffled - the tricks of the previous round, picked up as
        they lie - is dealt straight away: cutting it would only break the order
        that counting the cards depends on.
        """
        if self._deck_is_shuffled:
            self.phase = Phase.WAITING_FOR_CUT
            return []
        return self._deal()

    def _apply_cut(self, seat: Seat, action: Cut) -> list[Event]:
        low = self.ruleset.deal.cut_minimum
        high = self.ruleset.deal.cut_maximum
        if not low <= action.count <= high:
            raise IllegalAction(f"je moet tussen {low} en {high} kaarten afnemen")

        count = action.count
        self._deck = self._deck[count:] + self._deck[:count]
        events: list[Event] = [DeckCut(seat=seat, count=count)]
        events.extend(self._deal())
        return events

    def _deal(self) -> list[Event]:
        # Index 0 is the turned trump; dealing works backwards from the end
        # of the deck so it's never touched by a packet.
        self.round.turned_trump = self._deck[0]
        # Whatever comes back on the table after this round is unshuffled.
        self._deck_is_shuffled = False

        hands: dict[Seat, list[Card]] = {seat: [] for seat in ALL_SEATS}
        order = seat_order_from(left_of(self.round.dealer))
        position = len(self._deck)
        for packet in self.ruleset.deal.packets:
            for seat in order:
                position -= packet
                hands[seat].extend(self._deck[position : position + packet])
        self._deck = self._deck[:position]

        self.round.hands = {seat: sort_for_hand(cards) for seat, cards in hands.items()}

        events: list[Event] = [
            CardsDealt(
                packets=tuple(self.ruleset.deal.packets),
                hands={seat: tuple(cards) for seat, cards in self.round.hands.items()},
            )
        ]

        self.round.troel = detect_troel(self.round.hands)
        self.phase = Phase.BIDDING

        if self.round.troel is not None:
            troel = self.round.troel
            for seat in (troel.lead, troel.partner):
                entry = BidEntry(seat=seat, bid=Bid(BidType.TROEL, suit=troel.trump), forced=True)
                self.round.bids.append(entry)
                events.append(BidPlaced(seat=seat, bid=entry.bid, forced=True))
            if self.ruleset.bidding.troel_above_all and not self.ruleset.bidding.troel_beaten_by:
                # Nothing can outbid it, so play starts immediately and the
                # turned trump is never shown.
                events.append(BiddingFinished())
                events.extend(self._establish_contract())
                return events

        if self.round.turned_trump is not None:
            events.append(TrumpTurned(dealer=self.round.dealer, card=self.round.turned_trump))
        return events

    def _apply_bid(self, seat: Seat, action: PlaceBid) -> list[Event]:
        options = self.ladder.options_after(self.round.bids, seat)
        bid = action.bid
        allowed = next(
            (
                option
                for option in options
                if option.type is bid.type and option.tricks == bid.tricks
            ),
            None,
        )
        if allowed is None:
            raise IllegalAction(f"'{bid}' mag je nu niet bieden")
        if self.ladder.needs_suit(bid) and bid.suit is None:
            raise IllegalAction("je moet een troefkleur kiezen bij dit bod")
        if allowed.tricks is not None and bid.tricks is None:
            bid = Bid(type=bid.type, tricks=allowed.tricks, suit=bid.suit)

        self.round.bids.append(BidEntry(seat=seat, bid=bid))
        events: list[Event] = [BidPlaced(seat=seat, bid=bid)]

        next_seat = self._next_bidder()
        if next_seat is not None:
            self.round.seat_to_bid = next_seat
            return events

        events.append(BiddingFinished())
        events.extend(self._establish_contract())
        return events

    def _next_bidder(self) -> Seat | None:
        """Who bids next, or ``None`` when the bidding round is over."""
        voluntary = [entry for entry in self.round.bids if not entry.forced]

        if self.round.troel is not None:
            # After a troel only the contracts that may outbid it are offered,
            # one round around the table.
            if len(voluntary) >= 4:
                return None
            return left_of(self.round.seat_to_bid)

        if len(voluntary) < 4:
            return left_of(self.round.seat_to_bid)
        if len(voluntary) == 4 and self.ladder.is_final_say(self.round.bids):
            asker = self.ladder.asker(self.round.bids)
            return asker
        return None

    def _establish_contract(self) -> list[Event]:
        outcome = resolve_contract(
            self.round.bids,
            self.ladder,
            self.ruleset,
            dealer=self.round.dealer,
            turned_trump=self.round.turned_trump,
            troel=self.round.troel,
        )
        if isinstance(outcome, RedealReason):
            return self._redeal(outcome)

        self.round.contract = outcome
        self.round.trump = outcome.trump  # type: ignore[assignment]
        self.round.to_play = Seat(outcome.leader)
        self.phase = Phase.PLAYING
        return [ContractEstablished(contract=outcome, trump=outcome.trump)]  # type: ignore[arg-type]

    def _apply_play(self, seat: Seat, action: PlayCard) -> list[Event]:
        card = action.card
        hand = self.round.hands[seat]
        if card not in hand:
            raise IllegalAction("die kaart zit niet in je hand")
        legal = self._legal_cards(seat)
        if card not in legal:
            raise IllegalAction(self._why_illegal(card, legal))

        hand.remove(card)
        self.round.trick.append(PlayedCard(seat=seat, card=card))
        events: list[Event] = [
            CardPlayed(seat=seat, card=card, position_in_trick=len(self.round.trick))
        ]

        if len(self.round.trick) < len(ALL_SEATS):
            self.round.to_play = left_of(seat)
            return events

        events.extend(self._complete_trick())
        return events

    def _why_illegal(self, card: Card, legal: Sequence[Card]) -> str:
        led = self.round.trick[0].card.suit if self.round.trick else None
        if led is not None and card.suit is not led:
            return f"je moet kleur volgen ({_suit_nl(led)})"
        if len(legal) == 1:
            return f"je moet nu {legal[0].code} spelen"
        return "die kaart mag je nu niet spelen"

    def _complete_trick(self) -> list[Event]:
        contract = self.round.contract
        assert contract is not None
        winner = trick_winner(self.round.trick, self.round.trump)

        won = tuple(played.card for played in self.round.trick)
        if int(winner) in contract.declarers:
            self.round.declarer_won.append(won)
        else:
            self.round.defender_won.append(won)

        cards = tuple((played.seat, played.card) for played in self.round.trick)
        events: list[Event] = [
            TrickCompleted(
                winner=winner,
                cards=cards,
                declarer_tricks=self.round.declarer_tricks,
                defender_tricks=self.round.defender_tricks,
            )
        ]

        self.round.last_trick = tuple(self.round.trick)
        self.round.trick = []
        self.round.tricks_played += 1
        self.round.to_play = winner

        if self.round.tricks_played == CARDS_PER_HAND:
            events.extend(self._score_round())
            return events

        events.extend(self._announce_if_the_contract_just_died())
        return events

    def _announce_if_the_contract_just_died(self) -> list[Event]:
        """Say so once, the first trick after the contract becomes unmakeable.

        Players reasonably assume a dead contract makes the rest of the round
        pointless. For a solo contract it is, and the declaring side may stop
        there and then. For a duo contract it is not: the penalty is charged per
        missing trick, so what happens next still moves money, and nothing else
        would tell them that. The event carries which of the two it is.
        """
        contract = self.round.contract
        if contract is None or self.round.contract_lost_announced:
            return []
        if contract.can_still_be_made(self.round.declarer_tricks, self.tricks_remaining()):
            return []
        self.round.contract_lost_announced = True
        return [
            ContractLost(
                contract=contract,
                folding_offered=self.folding_is_offered(),
                payout_settled=self.payout_is_settled(),
            )
        ]

    def _score_round(self, *, folded: bool = False) -> list[Event]:
        contract = self.round.contract
        assert contract is not None
        result = RoundResult(
            contract=contract,
            tricks_made=self.round.declarer_tricks,
            multiplier=self.round.multiplier,
        )
        deltas = score_round(result, self.scale)
        for seat, delta in deltas.items():
            self.totals[seat] += delta

        self.round.to_play = None
        self.phase = Phase.ROUND_FINISHED
        self._collect_cards()

        events: list[Event] = [
            RoundScored(
                contract=contract,
                tricks_made=result.tricks_made,
                made=result.made,
                deltas=dict(deltas),
                totals=dict(self.totals),
                folded=folded,
            )
        ]

        target = self.ruleset.play.round_count
        if target and self.round_number >= target:
            self.phase = Phase.GAME_FINISHED
            events.append(GameFinished(totals=dict(self.totals)))
        return events

    def _collect_cards(self) -> None:
        """Gather every card back into the deck.

        Traditional wiezen does not reshuffle between rounds - the tricks stay
        lying as they were won - so the order matters. Ported from the old
        ``collect_cards`` (hands, starting left of the dealer) and the tail of
        ``process_game`` (won tricks, declarers before defenders).
        """
        for seat in seat_order_from(left_of(self.round.dealer)):
            self._deck.extend(self.round.hands.get(seat, []))
            self.round.hands[seat] = []
        # A fold can land halfway through a trick, leaving cards on the table
        # that nobody won. They are scooped up with the hands, which is what
        # happens in the flesh. Empty after a round that ran its full course.
        self._deck.extend(played.card for played in self.round.trick)
        self.round.trick = []
        for won in [*self.round.declarer_won, *self.round.defender_won]:
            self._deck.extend(won)
        self.round.declarer_won.clear()
        self.round.defender_won.clear()

        if len(set(self._deck)) != len(self._deck) or len(self._deck) != DECK_SIZE:
            raise AssertionError(
                f"kaarten kwijtgeraakt bij het ophalen: {len(self._deck)} kaarten, "
                f"{len(set(self._deck))} uniek"
            )

    # --- views ------------------------------------------------------------

    def hand_of(self, seat: Seat) -> tuple[Card, ...]:
        return tuple(self.round.hands.get(seat, []))

    def open_hands(self) -> dict[Seat, tuple[Card, ...]]:
        """Hands that lie face up (misere ouverte)."""
        contract = self.round.contract
        if contract is None or not contract.spec.open_hand:
            return {}
        return {Seat(seat): self.hand_of(Seat(seat)) for seat in contract.declarers}


def _suit_nl(suit: Suit) -> str:
    return {
        Suit.CLUBS: "klaveren",
        Suit.DIAMONDS: "koeken",
        Suit.HEARTS: "harten",
        Suit.SPADES: "schoppen",
    }[suit]
