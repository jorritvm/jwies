"""Turning engine events into protocol messages with Dutch text.

This is the only module (besides ``chat``) allowed to produce player-visible
sentences. The engine speaks in typed events with English names; everything a
player reads is rendered here from the text catalog.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from jwies_core.bidding import Bid, BidType
from jwies_core.cards import Card, Suit
from jwies_core.contracts import Contract
from jwies_core.engine import Prompt as EnginePrompt
from jwies_core.events import (
    BidPlaced,
    CardPlayed,
    ContractEstablished,
    DealerAnnounced,
    Event,
    GameFinished,
    RedealRequired,
    RoundScored,
    TrickCompleted,
    TrumpTurned,
)
from jwies_core.seats import Seat
from jwies_protocol import (
    BidInfo,
    ContractInfo,
    Prompt,
    PromptKindCode,
    ServerMessage,
    SuitCode,
    TrickCounts,
    server_messages,
)

from jwies_server.texts import TextCatalog

__all__ = ["Presenter"]


def _decimal(value: Decimal) -> str:
    """Money on the wire is a string, so no float drift can creep in."""
    normalised = value.normalize()
    text = format(normalised, "f")
    return text if text != "-0" else "0"


class Presenter:
    """Renders engine events for a specific table."""

    def __init__(self, catalog: TextCatalog, names: dict[Seat, str]) -> None:
        self.catalog = catalog
        self.names = names

    def name_of(self, seat: Seat) -> str:
        return self.names.get(seat, f"stoel {int(seat) + 1}")

    # --- small pieces ------------------------------------------------------

    def suit_name(self, suit: Suit | None, *, upper: bool = True) -> str:
        if suit is None:
            return self.catalog.render("suit.none")
        key = f"suit.{suit.value}" if upper else f"suit_lower.{suit.value}"
        return self.catalog.render(key)

    def contract_name(self, contract: Contract) -> str:
        return self.catalog.render(f"contract.name.{contract.key.value}")

    def bid_announcement(self, seat: Seat, bid: Bid) -> str:
        """The Dutch call a player makes, lifted from the old client's bid()."""
        speler = self.name_of(seat)
        match bid.type:
            case BidType.PASS:
                return self.catalog.render("bid.pass", speler=speler)
            case BidType.ASK:
                return self.catalog.render("bid.ask", speler=speler, troef=self.suit_name(bid.suit))
            case BidType.JOIN:
                return self.catalog.render("bid.join", speler=speler)
            case BidType.ALONE:
                return self.catalog.render("bid.alone", speler=speler, slagen=bid.tricks or 5)
            case BidType.ABONDANCE:
                return self.catalog.render(
                    "bid.abondance",
                    speler=speler,
                    slagen=bid.tricks or 9,
                    troef=self.suit_name(bid.suit),
                )
            case BidType.MISERE:
                return self.catalog.render("bid.misere", speler=speler)
            case BidType.MISERE_OUVERTE:
                return self.catalog.render("bid.misere_ouverte", speler=speler)
            case BidType.SOLO:
                return self.catalog.render(
                    "bid.solo", speler=speler, troef=self.suit_name(bid.suit)
                )
            case BidType.SOLO_SLIM:
                return self.catalog.render("bid.solo_slim", speler=speler)
            case BidType.TROEL:
                return self.catalog.render("bid.troel", speler=speler)
            case BidType.PICO:
                return self.catalog.render("bid.pico", speler=speler)
        return ""

    # --- conversions -------------------------------------------------------

    @staticmethod
    def bid_info(bid: Bid) -> BidInfo:
        return BidInfo(
            type=bid.type.value,  # type: ignore[arg-type]
            tricks=bid.tricks,
            suit=SuitCode(bid.suit.value) if bid.suit else None,
        )

    def contract_info(self, contract: Contract) -> ContractInfo:
        trump = contract.trump
        return ContractInfo(
            key=contract.key.value,  # type: ignore[arg-type]
            name=self.contract_name(contract),
            tricks_required=contract.tricks_required,
            declarers=tuple(contract.declarers),
            defenders=tuple(contract.defenders),
            trump=SuitCode(trump.value) if isinstance(trump, Suit) else None,
            open_hand=contract.spec.open_hand,
        )

    def prompt(self, prompt: EnginePrompt) -> Prompt:
        return Prompt(
            kind=PromptKindCode(prompt.kind.value),
            bid_options=tuple(self.bid_info(bid) for bid in prompt.bid_options),
            legal_cards=tuple(card.code for card in prompt.legal_cards),
            cut_minimum=prompt.cut_minimum,
            cut_maximum=prompt.cut_maximum,
        )

    def contract_sentence(self, contract: Contract) -> str:
        players = " en ".join(self.name_of(Seat(seat)) for seat in contract.declarers)
        trump = contract.trump
        if isinstance(trump, Suit):
            trump_part = self.catalog.render(
                "contract.with_trump", troef=self.suit_name(trump, upper=False)
            )
        else:
            trump_part = self.catalog.render("contract.without_trump")
        key = (
            "contract.announced_team" if len(contract.declarers) > 1 else "contract.announced_solo"
        )
        return self.catalog.render(
            key,
            spelers=players,
            contract=self.contract_name(contract),
            slagen=contract.tricks_required,
            troefzin=trump_part,
        )

    # --- events ------------------------------------------------------------

    def messages_for(self, event: Event) -> list[ServerMessage]:
        """Public messages for one engine event.

        Private per-seat messages (hands, prompts) are handled by the lobby
        runtime, which knows who may see what.
        """
        match event:
            case DealerAnnounced():
                messages: list[ServerMessage] = [
                    server_messages.RoundStarted(
                        round_number=event.round_number,
                        dealer_seat=int(event.dealer),
                        multiplier=_decimal(event.multiplier),
                    ),
                    self.chat(
                        self.catalog.render(
                            "round.started",
                            ronde=event.round_number,
                            speler=self.name_of(event.dealer),
                        )
                    ),
                ]
                if event.multiplier != 1:
                    messages.append(
                        self.chat(
                            self.catalog.render(
                                "round.multiplier", factor=_decimal(event.multiplier)
                            )
                        )
                    )
                return messages

            case TrumpTurned():
                return [
                    server_messages.TrumpTurned(
                        dealer_seat=int(event.dealer), card=event.card.code
                    ),
                    self.chat(self.catalog.render("game.trump_turned", kaart=event.card.code)),
                ]

            case BidPlaced():
                announcement = self.bid_announcement(event.seat, event.bid)
                return [
                    server_messages.BidPlaced(
                        seat=int(event.seat),
                        bid=self.bid_info(event.bid),
                        forced=event.forced,
                        announcement=announcement,
                    ),
                    self.chat(announcement),
                ]

            case RedealRequired():
                text = self.catalog.render(f"redeal.{event.reason}")
                return [
                    server_messages.Redeal(reason=event.reason, text=text),
                    self.chat(text),
                ]

            case ContractEstablished():
                text = self.contract_sentence(event.contract)
                return [
                    server_messages.TrumpHidden(),
                    server_messages.ContractEstablished(
                        contract=self.contract_info(event.contract), text=text
                    ),
                    self.chat(text),
                ]

            case CardPlayed():
                return [
                    server_messages.CardPlayed(
                        seat=int(event.seat),
                        card=event.card.code,
                        position_in_trick=event.position_in_trick,
                    )
                ]

            case TrickCompleted():
                text = self.catalog.render("trick.winner", speler=self.name_of(event.winner))
                return [
                    server_messages.TrickCompleted(
                        winner_seat=int(event.winner),
                        cards=tuple(
                            {"seat": int(seat), "card": card.code}  # type: ignore[misc]
                            for seat, card in event.cards
                        ),
                        trick_counts=TrickCounts(
                            declarers=event.declarer_tricks,
                            defenders=event.defender_tricks,
                        ),
                        text=text,
                    ),
                    self.chat(text),
                ]

            case RoundScored():
                return self._round_scored(event)

            case GameFinished():
                totals = {
                    self.name_of(seat): _decimal(value) for seat, value in event.totals.items()
                }
                text = self.catalog.render("game.finished")
                return [
                    server_messages.GameFinished(totals=totals, text=text),
                    self.chat(text),
                ]

            case _:
                return []

    def _round_scored(self, event: RoundScored) -> list[ServerMessage]:
        key = "round.made" if event.made else "round.failed"
        headline = self.catalog.render(
            key, slagen=event.tricks_made, nodig=event.contract.tricks_required
        )
        deltas = {self.name_of(seat): _decimal(value) for seat, value in event.deltas.items()}
        totals = {self.name_of(seat): _decimal(value) for seat, value in event.totals.items()}

        lines = [headline, self.catalog.render("round.points_header")]
        for seat, delta in event.deltas.items():
            lines.append(
                self.catalog.render(
                    "round.points_line",
                    speler=self.name_of(seat),
                    delta=_decimal(delta),
                    totaal=_decimal(event.totals[seat]),
                )
            )
        text = "\n".join(lines)

        return [
            server_messages.RoundFinished(
                tricks_made=event.tricks_made,
                made=event.made,
                deltas=deltas,
                totals=totals,
                text=text,
            ),
            self.chat(text),
        ]

    # --- helpers -----------------------------------------------------------

    def chat(self, text: str, *, private: bool = False) -> server_messages.Chat:
        return server_messages.Chat(
            kind=server_messages.ChatKind.SERVER, text=text, private=private
        )

    def system(self, text: str) -> server_messages.Chat:
        return server_messages.Chat(kind=server_messages.ChatKind.SYSTEM, text=text)

    def error(self, code: str, text: str) -> server_messages.Error:
        return server_messages.Error(code=code, text=text)  # type: ignore[arg-type]

    def cards(self, cards: Iterable[Card]) -> tuple[str, ...]:
        return tuple(card.code for card in cards)
