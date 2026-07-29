"""Protocol models: round-trips, discrimination, and parity with the engine."""

from __future__ import annotations

import json
from typing import get_args

import pytest
from jwies_protocol import (
    PROTOCOL_VERSION,
    BidInfo,
    BidTypeCode,
    ClientEnvelope,
    ClientKind,
    ClientMessage,
    ContractKeyCode,
    PhaseCode,
    PromptKindCode,
    ServerEnvelope,
    ServerMessage,
    SuitCode,
    client_messages,
    server_messages,
)
from pydantic import TypeAdapter, ValidationError

CLIENT = TypeAdapter(ClientMessage)
SERVER = TypeAdapter(ServerMessage)


def test_a_client_envelope_round_trips_through_json() -> None:
    envelope = ClientEnvelope(
        id="abc",
        msg=client_messages.PlayCard(card="AH"),
    )
    raw = envelope.model_dump_json()
    back = ClientEnvelope.model_validate_json(raw)
    assert back == envelope
    assert json.loads(raw)["msg"]["type"] == "play_card"


def test_a_server_envelope_round_trips_through_json() -> None:
    envelope = ServerEnvelope(
        seq=7,
        msg=server_messages.Chat(kind=server_messages.ChatKind.SERVER, text="Welkom!"),
    )
    back = ServerEnvelope.model_validate_json(envelope.model_dump_json())
    assert back.msg.text == "Welkom!"  # type: ignore[union-attr]
    assert back.seq == 7
    assert back.v == PROTOCOL_VERSION


def test_unknown_message_type_is_rejected_not_silently_accepted() -> None:
    with pytest.raises(ValidationError):
        CLIENT.validate_python({"type": "definitely_not_a_message"})


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CLIENT.validate_python({"type": "ping", "sneaky": 1})


def test_card_codes_are_validated() -> None:
    CLIENT.validate_python({"type": "play_card", "card": "10S"})
    for bad in ("XX", "1S", "AHH", "ah"):
        with pytest.raises(ValidationError):
            CLIENT.validate_python({"type": "play_card", "card": bad})


def test_usernames_are_validated() -> None:
    CLIENT.validate_python({"type": "hello", "username": "Jan-Piet", "client": "web"})
    for bad in ("x", "a" * 21, "Jan;DROP"):
        with pytest.raises(ValidationError):
            CLIENT.validate_python({"type": "hello", "username": bad, "client": "web"})


def test_a_browser_style_raw_dict_parses() -> None:
    # The web client sends hand-built JSON, not pydantic output. This is the
    # shape it produces.
    raw = {
        "v": 1,
        "id": "1",
        "msg": {
            "type": "place_bid",
            "bid": {"type": "abondance", "tricks": 10, "suit": "S"},
        },
    }
    envelope = ClientEnvelope.model_validate(raw)
    assert isinstance(envelope.msg, client_messages.PlaceBid)
    assert envelope.msg.bid.tricks == 10
    assert envelope.msg.bid.suit is SuitCode.SPADES


def test_optional_bid_fields_may_be_omitted() -> None:
    bid = BidInfo.model_validate({"type": "pass"})
    assert bid.tricks is None and bid.suit is None


# --- parity with the engine's own enums --------------------------------------


def test_suit_codes_match_the_engine() -> None:
    from jwies_core.cards import Suit

    assert {member.value for member in SuitCode} == {member.value for member in Suit}


def test_bid_type_codes_match_the_engine() -> None:
    from jwies_core.bidding import BidType

    assert {member.value for member in BidTypeCode} == {member.value for member in BidType}


def test_contract_key_codes_match_the_engine() -> None:
    from jwies_core.contracts import ContractKey

    assert {member.value for member in ContractKeyCode} == {member.value for member in ContractKey}


def test_phase_codes_match_the_engine() -> None:
    from jwies_core.engine import Phase

    assert {member.value for member in PhaseCode} == {member.value for member in Phase}


def test_prompt_kind_codes_match_the_engine() -> None:
    from jwies_core.engine import PromptKind

    assert {member.value for member in PromptKindCode} == {member.value for member in PromptKind}


def test_client_kinds_cover_both_clients() -> None:
    assert {member.value for member in ClientKind} == {"qt", "web"}


# --- every message type is reachable ----------------------------------------


def _members(annotated_union: object) -> list[type]:
    """The concrete models inside an Annotated[A | B | ..., Field(...)] alias."""
    inner = get_args(annotated_union)[0]
    return list(get_args(inner))


@pytest.mark.parametrize(
    ("union", "label"),
    [(ClientMessage, "client"), (ServerMessage, "server")],
)
def test_every_message_has_a_unique_type_tag(union: object, label: str) -> None:
    tags = [model.model_fields["type"].default for model in _members(union)]
    assert tags, f"geen {label}-berichten gevonden"
    duplicates = {tag for tag in tags if tags.count(tag) > 1}
    assert not duplicates, f"dubbele {label}-berichttypes: {duplicates}"


def test_every_server_message_round_trips() -> None:
    # Guards against a model that cannot actually be serialised, e.g. because
    # of a field type JSON has no representation for.
    samples: list[ServerMessage] = [
        server_messages.Pong(),
        server_messages.PromptCleared(),
        server_messages.TableCleared(),
        server_messages.TrumpHidden(),
        server_messages.PhaseChanged(phase=PhaseCode.BIDDING),
        server_messages.CardPlayed(seat=2, card="QD", position_in_trick=3),
        server_messages.RoundFinished(
            tricks_made=8, made=True, deltas={"Jan": "2"}, totals={"Jan": "2"}, text="ok"
        ),
    ]
    for message in samples:
        raw = ServerEnvelope(msg=message).model_dump_json()
        assert ServerEnvelope.model_validate_json(raw).msg == message


def test_contract_key_codes_are_all_representable() -> None:
    for key in ContractKeyCode:
        assert isinstance(key.value, str)
