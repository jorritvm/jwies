"""Sessions and chat commands."""

from __future__ import annotations

import unicodedata
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

    @pytest.mark.parametrize(
        "name",
        [
            "Jan",
            "Jan-Piet",
            "speler 1",
            "a_b",
            "ab",
            # People are not spelled in ASCII: these are the ones that used to be
            # refused, and refused with the wrong sentence at that.
            "José",
            "O'Brien",
            "Jorrit.VM",
            "Ann-Sofie",
            "Жан",
            "山田",
            "  Jan  ",  # trimmed, not refused
        ],
    )
    def test_valid_usernames(self, name: str) -> None:
        assert SessionRegistry.is_valid_username(name)

    @pytest.mark.parametrize(
        "name",
        [
            "a",
            "",
            "   ",
            "x" * 21,
            "Jan;drop",
            "<script>",
            "Jan&Co",
            'zeg "hallo"',
            "regel\nbreuk",
            "...",  # punctuation is not a name
        ],
    )
    def test_invalid_usernames(self, name: str) -> None:
        assert not SessionRegistry.is_valid_username(name)

    def test_the_two_spellings_of_an_accent_are_one_player(self) -> None:
        """``é`` is one character or two, depending on who typed it.

        A Mac hands over the decomposed form and Windows the composed one, so
        without normalising, the same player returning on the other machine is a
        stranger to the registry - new session, new seat, and the old one left
        sitting there waiting for someone who is already back.

        Both forms are derived rather than typed as literals: they look
        identical on screen, so an editor that helpfully normalised this file
        would turn the test into a tautology without anyone noticing.
        """
        composed = unicodedata.normalize("NFC", "José")  # one character
        decomposed = unicodedata.normalize("NFD", "José")  # e + combining acute
        assert composed != decomposed
        assert (len(composed), len(decomposed)) == (4, 5)

        registry = SessionRegistry()
        first, _ = registry.resolve_hello(composed, None)
        first.disconnect()
        again, outcome = registry.resolve_hello(decomposed, None)
        assert again is first
        assert outcome is HelloOutcome.REBOUND
        assert first.username == composed
        assert SessionRegistry.is_valid_username(decomposed)


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

        # Taken from the fixtures rather than spelled out: what is under test is
        # that the command renders the configured name at all. Hardcoding it
        # meant renaming a scale in config/ failed this test, which says nothing
        # about the command and everything about the assertion.
        ruleset_text = "\n".join(handle_chat_command("!ruleset", context))
        assert klassiek.name in ruleset_text
        assert "pakjes" in ruleset_text  # Dutch aliases, not English field names

        counting_text = "\n".join(handle_chat_command("!counting", context))
        assert schaal_a.name in counting_text
        assert "tegenstander" in counting_text
        assert "solo_slim" in counting_text

        score_text = "\n".join(handle_chat_command("!score", context))
        assert "nog geen" in score_text  # no game running yet


class TestTheDeadContractAnnouncement:
    """The one sentence that has to change a player's mind.

    Seeing "solo slim is niet meer te halen" and then being made to play on
    looks like the game is wasting your time. Whether it is depends on the
    contract: a duo contract is charged per missing trick, so the rest of the
    round is still worth money and giving up costs you. If the sentence does
    not say which case this is, nobody will believe it either way.
    """

    @staticmethod
    def _lost(*, folding_offered: bool, payout_settled: bool) -> object:
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
        return ContractLost(
            contract=contract,
            folding_offered=folding_offered,
            payout_settled=payout_settled,
        )

    def _sentence(self, *, folding_offered: bool = True, payout_settled: bool) -> str:
        from jwies_server.presenter import Presenter

        messages = Presenter({}).messages_for(
            self._lost(folding_offered=folding_offered, payout_settled=payout_settled)
        )
        assert len(messages) == 1
        return str(messages[0].text)

    def test_it_warns_that_giving_up_is_not_free(self) -> None:
        sentence = self._sentence(payout_settled=False)
        assert "solo slim" in sentence
        assert "niet meer te halen" in sentence
        assert "mag opgeven" in sentence
        assert "per ontbrekende slag" in sentence, "zonder de reden is het gewoon vervelend"

    def test_it_says_so_when_there_is_nothing_left_to_lose(self) -> None:
        sentence = self._sentence(payout_settled=True)
        assert "punten liggen vast" in sentence
        assert "mag de ronde opgeven" in sentence
        assert "per ontbrekende slag" not in sentence

    def test_a_ruleset_that_forbids_folding_just_states_the_fact(self) -> None:
        sentence = self._sentence(folding_offered=False, payout_settled=True)
        assert sentence == "solo slim is niet meer te halen."


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
