"""Sessions and chat commands."""

from __future__ import annotations

from typing import ClassVar

import pytest

from jwies_core.config import Ruleset, ScoringScale
from jwies_server.chat import COMMANDS, ChatContext, handle_chat_command, is_command
from jwies_server.sessions import HelloOutcome, SessionRegistry


class TestSessions:
    def test_an_unknown_username_creates_a_session(self) -> None:
        registry = SessionRegistry()
        session, outcome = registry.resolve_hello("Jan", None)
        assert outcome is HelloOutcome.NEW
        assert session.resume_token

    def test_a_matching_token_resumes(self) -> None:
        registry = SessionRegistry()
        session, _ = registry.resolve_hello("Jan", None)
        session.disconnect()
        again, outcome = registry.resolve_hello("Jan", session.resume_token)
        assert outcome is HelloOutcome.RESUMED
        assert again is session

    def test_a_dead_session_rebinds_without_a_token(self) -> None:
        # The requirement: the username is the key.
        registry = SessionRegistry()
        session, _ = registry.resolve_hello("Jan", None)
        session.disconnect()
        again, outcome = registry.resolve_hello("Jan", None)
        assert outcome is HelloOutcome.REBOUND
        assert again is session

    def test_a_live_session_is_defended(self) -> None:
        registry = SessionRegistry()
        session, _ = registry.resolve_hello("Jan", None)
        session.agent = object()  # type: ignore[assignment]
        _, outcome = registry.resolve_hello("Jan", "wrong-token")
        assert outcome is HelloOutcome.TAKEN

    def test_usernames_are_case_insensitively_unique(self) -> None:
        registry = SessionRegistry()
        first, _ = registry.resolve_hello("Jan", None)
        first.disconnect()
        second, outcome = registry.resolve_hello("JAN", None)
        assert second is first
        assert outcome is HelloOutcome.REBOUND

    @pytest.mark.parametrize("name", ["Jan", "Jan-Piet", "speler 1", "a_b", "ab"])
    def test_valid_usernames(self, name: str) -> None:
        assert SessionRegistry.is_valid_username(name)

    @pytest.mark.parametrize("name", ["a", "", "x" * 21, "Jan;drop", "<script>"])
    def test_invalid_usernames(self, name: str) -> None:
        assert not SessionRegistry.is_valid_username(name)


class TestChatCommands:
    def test_command_detection(self) -> None:
        assert is_command("!help")
        assert not is_command("gewoon een zin")

    def test_help_lists_every_registered_command(self) -> None:
        body = "\n".join(handle_chat_command("!help", ChatContext(lobby=None, session=None)))  # type: ignore[arg-type]
        for name in COMMANDS:
            assert f"!{name}" in body, f"!{name} ontbreekt in !help"

    def test_unknown_command_is_reported_in_dutch(self) -> None:
        lines = handle_chat_command("!bestaatniet", ChatContext(lobby=None, session=None))  # type: ignore[arg-type]
        assert "Onbekend commando" in lines[0]

    def test_ruleset_and_counting_render_dutch(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        class FakeLobby:
            ruleset = klassiek
            scoring = schaal_a
            engine = None
            members: ClassVar[dict[str, object]] = {}

        context = ChatContext(lobby=FakeLobby(), session=None)  # type: ignore[arg-type]

        ruleset_text = "\n".join(handle_chat_command("!ruleset", context))
        assert "Klassiek wiezen" in ruleset_text
        assert "pakjes" in ruleset_text  # Dutch aliases, not English field names

        counting_text = "\n".join(handle_chat_command("!counting", context))
        assert "Schaal A" in counting_text
        assert "tegenstander" in counting_text
        assert "solo_slim" in counting_text

        score_text = "\n".join(handle_chat_command("!score", context))
        assert "nog geen" in score_text  # no game running yet


class TestTheDeadContractAnnouncement:
    """The one sentence that has to change a player's mind.

    Seeing "solo slim is niet meer te halen" and then being made to play on
    looks like the game is wasting your time. It is not: the penalty is charged
    per missing trick, so the rest of the round is still worth money. If that
    sentence does not say why, nobody will believe it.
    """

    @staticmethod
    def _lost(*, folding_offered: bool) -> object:
        from jwies_core.contracts import CONTRACT_CATALOG, Contract, ContractKey
        from jwies_core.events import ContractLost

        spec = CONTRACT_CATALOG[ContractKey.SOLO_SLIM]
        contract = Contract(
            spec=spec,
            declarers=(0,),
            defenders=(1, 2, 3),
            trump=None,
            tricks_required=13,
            leader=0,
        )
        return ContractLost(contract=contract, folding_offered=folding_offered)

    def _sentence(self, *, folding_offered: bool) -> str:
        from jwies_server.presenter import Presenter

        messages = Presenter({}).messages_for(self._lost(folding_offered=folding_offered))
        assert len(messages) == 1
        return str(messages[0].text)

    def test_it_explains_why_the_round_carries_on(self) -> None:
        sentence = self._sentence(folding_offered=False)
        assert "solo slim" in sentence
        assert "niet meer te halen" in sentence
        assert "per ontbrekende slag" in sentence, "zonder de reden is het gewoon vervelend"

    def test_it_offers_the_way_out_when_there_is_one(self) -> None:
        sentence = self._sentence(folding_offered=True)
        assert "mag de ronde stoppen" in sentence
        assert "per ontbrekende slag" not in sentence


class TestDutchSentences:
    """The server renders every player-visible sentence, so nothing may be missing.

    These used to be catalog-key checks. The sentences are literals now, so what
    is worth asserting is that the two lookup tables the presenter still needs
    cover every value the engine can produce - the only remaining way to get a
    ``KeyError`` in front of a player.
    """

    def test_every_contract_has_a_dutch_name(self) -> None:
        from jwies_core.contracts import CONTRACT_CATALOG
        from jwies_server.presenter import CONTRACT_NAMES

        for key in CONTRACT_CATALOG:
            assert key in CONTRACT_NAMES

    def test_every_suit_has_a_dutch_name_in_both_casings(self) -> None:
        from jwies_core.cards import Suit
        from jwies_server.presenter import Presenter

        for suit in [*Suit, None]:
            assert Presenter.suit_name(suit).isupper()
            assert Presenter.suit_name(suit, upper=False).islower()

    def test_every_redeal_reason_has_a_sentence(self) -> None:
        from jwies_core.resolution import RedealReason
        from jwies_server.presenter import REDEAL_REASONS

        for reason in RedealReason:
            assert reason.value in REDEAL_REASONS
