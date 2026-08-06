"""Turning engine events into protocol messages with Dutch text.

This is the only module (besides ``chat``) that produces player-visible
sentences. The engine speaks in typed events with English names; everything a
player reads is written out here.

The sentences are literals rather than keys into a catalog, deliberately. jwies
is Vlaamse wies, played in Dutch; the enum values, error messages, config
aliases and chat commands are Dutch throughout the codebase already, and there
is no second language planned. Under those conditions a catalog buys nothing and
costs a file lookup every time you want to know what a line actually says. If a
second language ever becomes a real goal, this module and ``chat`` are the two
places to extract from, and they are the only ones.
"""

from __future__ import annotations

from decimal import Decimal

from jwies_core.bidding import Bid, BidType
from jwies_core.cards import Suit
from jwies_core.contracts import Contract, ContractKey
from jwies_core.engine import Prompt
from jwies_core.events import (
    BidPlaced,
    CardPlayed,
    ContractEstablished,
    ContractLost,
    DealerAnnounced,
    Event,
    FoldingChanged,
    GameFinished,
    RedealRequired,
    RoundScored,
    TrickCompleted,
    TrumpTurned,
)
from jwies_core.seats import Seat

# Qualified rather than imported by name: half of the engine's event types share
# a name with the wire message they turn into, which is the clearest possible
# sign that they are two different things.
from jwies_server import protocol

__all__ = ["Presenter"]

# Shouted in a call ("IK GA HARTEN VRAGEN"), lowercased when part of a sentence.
SUIT_NAMES: dict[Suit | None, str] = {
    Suit.CLUBS: "KLAVEREN",
    Suit.DIAMONDS: "KOEKEN",
    Suit.HEARTS: "HARTEN",
    Suit.SPADES: "SCHOPPEN",
    None: "ZONDER TROEF",
}

CONTRACT_NAMES: dict[ContractKey, str] = {
    ContractKey.ALLIANCE: "vragen en meegaan",
    ContractKey.ALONE: "alleen gaan",
    ContractKey.PICO: "pico",
    ContractKey.ABONDANCE_9: "abondance 9",
    ContractKey.ABONDANCE_9_TRUMP: "abondance in troef",
    ContractKey.ABONDANCE_10: "abondance 10",
    ContractKey.ABONDANCE_11: "abondance 11",
    ContractKey.ABONDANCE_12: "abondance 12",
    ContractKey.MISERE: "miserie",
    ContractKey.MISERE_OUVERTE: "miserie bloot",
    ContractKey.TROEL: "troel",
    ContractKey.SOLO: "solo",
    ContractKey.SOLO_SLIM: "solo slim",
}

REDEAL_REASONS = {
    "all_passed": "Iedereen heeft gepast. Dezelfde deler deelt opnieuw.",
    "ask_declined": (
        "Er werd gevraagd, niemand ging mee en de vrager gaat niet alleen. "
        "De volgende speler deelt."
    ),
}


def _decimal(value: Decimal) -> str:
    """Money on the wire is a string, so no float drift can creep in."""
    normalised = value.normalize()
    text = format(normalised, "f")
    return text if text != "-0" else "0"


class Presenter:
    """Renders engine events for a specific table."""

    def __init__(self, names: dict[Seat, str]) -> None:
        self.names = names

    def name_of(self, seat: Seat) -> str:
        return self.names.get(seat, f"stoel {int(seat) + 1}")

    # --- small pieces ------------------------------------------------------

    @staticmethod
    def suit_name(suit: Suit | None, *, upper: bool = True) -> str:
        name = SUIT_NAMES[suit]
        return name if upper else name.lower()

    @staticmethod
    def contract_name(contract: Contract) -> str:
        return CONTRACT_NAMES[contract.key]

    def bid_announcement(self, seat: Seat, bid: Bid) -> str:
        """The Dutch call a player makes, lifted from the old client's bid()."""
        who = self.name_of(seat)
        suit = self.suit_name(bid.suit)
        match bid.type:
            case BidType.PASS:
                return f"{who}: IK PAS"
            case BidType.ASK:
                return f"{who}: IK GA {suit} VRAGEN"
            case BidType.JOIN:
                return f"{who}: IK GA MEE"
            case BidType.ALONE:
                return f"{who}: IK GA ALLEEN VOOR {bid.tricks or 5} SLAGEN"
            case BidType.ABONDANCE:
                return f"{who}: IK GA ABONDANCE {bid.tricks or 9} SLAGEN IN DE {suit}"
            case BidType.MISERE:
                return f"{who}: IK GA MISERIE"
            case BidType.MISERE_OUVERTE:
                return f"{who}: IK GA MISERIE BLOOT"
            case BidType.SOLO:
                return f"{who}: IK GA SOLO IN DE {suit}"
            case BidType.SOLO_SLIM:
                return f"{who}: IK GA SOLO SLIM"
            case BidType.TROEL:
                return f"{who}: TROEL!"
            case BidType.PICO:
                return f"{who}: IK GA PICO"
        return ""

    # --- conversions -------------------------------------------------------

    @staticmethod
    def bid_info(bid: Bid) -> protocol.BidInfo:
        return protocol.BidInfo(type=bid.type, tricks=bid.tricks, suit=bid.suit)

    def contract_info(self, contract: Contract) -> protocol.ContractInfo:
        trump = contract.trump
        return protocol.ContractInfo(
            key=contract.key,
            name=self.contract_name(contract),
            tricks_required=contract.tricks_required,
            declarers=tuple(contract.declarers),
            trump=trump if isinstance(trump, Suit) else None,
        )

    def prompt(self, prompt: Prompt) -> protocol.Prompt:
        return protocol.Prompt(
            kind=prompt.kind,
            bid_options=tuple(self.bid_info(bid) for bid in prompt.bid_options),
            legal_cards=tuple(card.code for card in prompt.legal_cards),
            cut_minimum=prompt.cut_minimum,
            cut_maximum=prompt.cut_maximum,
        )

    def contract_sentence(self, contract: Contract) -> str:
        players = " en ".join(self.name_of(Seat(seat)) for seat in contract.declarers)
        trump = contract.trump
        if isinstance(trump, Suit):
            troef = f" met {self.suit_name(trump, upper=False)} als troef"
        else:
            troef = " zonder troef"
        verb = "spelen samen" if len(contract.declarers) > 1 else "speelt"
        return (
            f"{players} {verb} {self.contract_name(contract)} "
            f"({contract.tricks_required} slagen){troef}."
        )

    # --- events ------------------------------------------------------------

    def messages_for(self, event: Event) -> list[protocol.ServerMessage]:
        """What one engine event puts on the wire.

        Most events produce only their Dutch sentence: the state they describe
        - who deals, what trump is, which bid was made, what the contract came
        out as - is in the snapshot that follows, so sending it twice would only
        create two ways for the clients to disagree. The exceptions are the
        trick messages, which describe a moment the snapshot cannot.
        """
        match event:
            case DealerAnnounced():
                messages: list[protocol.ServerMessage] = [
                    self.chat(
                        f"Ronde {event.round_number}. De deler is {self.name_of(event.dealer)}."
                    )
                ]
                if event.multiplier != 1:
                    messages.append(
                        self.chat(
                            "Iedereen paste vorige ronde: deze ronde telt "
                            f"{_decimal(event.multiplier)} keer."
                        )
                    )
                return messages

            case TrumpTurned():
                return [self.chat(f"De geblekte troefkaart is {event.card.code}.")]

            case BidPlaced():
                return [self.chat(self.bid_announcement(event.seat, event.bid))]

            case RedealRequired():
                return [self.chat(REDEAL_REASONS[event.reason])]

            case ContractEstablished():
                return [self.chat(self.contract_sentence(event.contract))]

            case CardPlayed():
                return [protocol.CardPlayed(seat=int(event.seat), card=event.card.code)]

            case TrickCompleted():
                text = f"{self.name_of(event.winner)} wint de slag."
                return [
                    protocol.TrickCompleted(
                        winner_seat=int(event.winner),
                        cards=tuple(
                            protocol.PlayedCardInfo(seat=int(seat), card=card.code)
                            for seat, card in event.cards
                        ),
                        trick_counts=protocol.TrickCounts(
                            declarers=event.declarer_tricks,
                            defenders=event.defender_tricks,
                        ),
                    ),
                    self.chat(text),
                ]

            case ContractLost():
                name = self.contract_name(event.contract)
                if not event.folding_offered:
                    return [self.chat(f"{name} is niet meer te halen.")]
                if event.payout_settled:
                    return [
                        self.chat(
                            f"{name} is niet meer te halen. De punten liggen vast, "
                            "dus de spelende partij mag de ronde opgeven."
                        )
                    ]
                # The counter-intuitive case, and the reason to say anything at
                # all: a dead contract is not a dead round.
                return [
                    self.chat(
                        f"{name} is niet meer te halen. De spelende partij mag opgeven, "
                        "maar de boete wordt per ontbrekende slag gerekend: elke slag "
                        "die ze nog binnenhaalt, scheelt punten."
                    )
                ]

            case FoldingChanged():
                if not event.folded:
                    return [self.chat("Er wordt toch verder gespeeld.")]
                names = ", ".join(sorted(self.name_of(seat) for seat in event.folded))
                return [self.chat(f"Wil opgeven: {names}.")]

            case RoundScored():
                return self._round_scored(event)

            case GameFinished():
                return [self.chat("Het spel is afgelopen.")]

            case _:
                return []

    def _round_scored(self, event: RoundScored) -> list[protocol.ServerMessage]:
        verdict = "Contract gehaald!" if event.made else "Contract niet gehaald:"
        lines = [
            f"{verdict} {event.tricks_made} van de {event.contract.tricks_required} "
            "beloofde slagen.",
        ]
        if event.folded:
            lines.append(
                "De spelende partij heeft opgegeven: de rest van de slagen is voor de tegenpartij."
            )
        lines.append("Punten deze ronde:")
        for seat, delta in event.deltas.items():
            lines.append(
                f"  {self.name_of(seat)}: {_decimal(delta)} (totaal {_decimal(event.totals[seat])})"
            )
        text = "\n".join(lines)

        return [
            protocol.RoundFinished(
                tricks_made=event.tricks_made,
                made=event.made,
                deltas={
                    self.name_of(seat): _decimal(value) for seat, value in event.deltas.items()
                },
                totals={
                    self.name_of(seat): _decimal(value) for seat, value in event.totals.items()
                },
                text=text,
            ),
            self.chat(text),
        ]

    # --- helpers -----------------------------------------------------------

    def chat(self, text: str) -> protocol.Chat:
        return protocol.Chat(kind=protocol.ChatKind.SERVER, text=text)

    def error(self, code: str, text: str) -> protocol.Error:
        return protocol.Error(code=code, text=text)  # type: ignore[arg-type]
