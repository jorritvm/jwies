"""Protocol models: round-trips, discrimination, and validation on the way in.

There is no enum-parity suite any more: the protocol's ``*Code`` names are
aliases of the engine's enums rather than copies of them, so the properties
those tests asserted are true by construction.
"""

from __future__ import annotations

import json
from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from jwies_server import protocol
from jwies_server.protocol import (
    PROTOCOL_VERSION,
    BidInfo,
    ClientEnvelope,
    ClientMessage,
    ContractKeyCode,
    ServerEnvelope,
    ServerMessage,
    SuitCode,
)
from jwies_server.sessions import SessionRegistry

CLIENT = TypeAdapter(ClientMessage)
SERVER = TypeAdapter(ServerMessage)


def test_a_client_envelope_round_trips_through_json() -> None:
    envelope = ClientEnvelope(msg=protocol.PlayCard(card="AH"))
    raw = envelope.model_dump_json()
    back = ClientEnvelope.model_validate_json(raw)
    assert back == envelope
    assert json.loads(raw)["msg"]["type"] == "play_card"


def test_a_server_envelope_round_trips_through_json() -> None:
    envelope = ServerEnvelope(
        seq=7,
        msg=protocol.Chat(kind=protocol.ChatKind.SERVER, text="Welkom!"),
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
        CLIENT.validate_python({"type": "lobby_list", "sneaky": 1})


def test_card_codes_are_validated() -> None:
    CLIENT.validate_python({"type": "play_card", "card": "10S"})
    for bad in ("XX", "1S", "AHH", "ah"):
        with pytest.raises(ValidationError):
            CLIENT.validate_python({"type": "play_card", "card": bad})


def test_an_unusable_username_still_parses() -> None:
    """The one field deliberately not validated by its type, and why.

    ``username`` used to be constrained here, which meant a name that broke the
    rules never reached the code that knows what the rules are: the envelope
    failed validation and the player was answered "onbegrijpelijk bericht" - for
    typing one letter, or an accent. Parsing has to succeed so ``_handshake``
    can refuse it with ``username_invalid`` and say what it expected.
    """
    for bad in ("x", "a" * 21, "Jan;DROP", "<script>", ""):
        message = CLIENT.validate_python({"type": "hello", "username": bad})
        assert message.username == bad
        assert not SessionRegistry.is_valid_username(bad)


def test_a_name_does_not_have_to_be_ascii() -> None:
    for name in ("Jan-Piet", "José", "O'Brien", "Жан"):
        message = CLIENT.validate_python({"type": "hello", "username": name})
        assert message.username == name
        assert SessionRegistry.is_valid_username(name)


def test_a_browser_style_raw_dict_parses() -> None:
    # The web client sends hand-built JSON, not pydantic output. This is the
    # shape it produces.
    raw = {
        "v": PROTOCOL_VERSION,
        "msg": {
            "type": "place_bid",
            "bid": {"type": "abondance", "tricks": 10, "suit": "S"},
        },
    }
    envelope = ClientEnvelope.model_validate(raw)
    assert isinstance(envelope.msg, protocol.PlaceBid)
    assert envelope.msg.bid.tricks == 10
    assert envelope.msg.bid.suit is SuitCode.SPADES


def test_an_envelope_from_an_older_client_still_parses() -> None:
    """So that a stale client is told to update, not called incomprehensible.

    ``ClientEnvelope`` is the one model that ignores unknown fields. Version 1
    carried an ``id`` for request/response correlation that nothing ever read; a
    client still sending it must get as far as the version check.
    """
    envelope = ClientEnvelope.model_validate(
        {"v": 1, "id": "7", "msg": {"type": "request_snapshot"}}
    )
    assert envelope.v == 1  # and the handshake will refuse it on that basis
    assert not hasattr(envelope, "id")


def test_the_messages_themselves_still_refuse_extras() -> None:
    """The envelope is lenient; what it carries is not."""
    with pytest.raises(ValidationError):
        ClientEnvelope.model_validate(
            {"v": PROTOCOL_VERSION, "msg": {"type": "request_snapshot", "sneaky": 1}}
        )


def test_optional_bid_fields_may_be_omitted() -> None:
    bid = BidInfo.model_validate({"type": "pass"})
    assert bid.tricks is None and bid.suit is None


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
        protocol.TableCleared(),
        protocol.CardPlayed(seat=2, card="QD"),
        protocol.RoundFinished(
            tricks_made=8, made=True, deltas={"Jan": "2"}, totals={"Jan": "2"}, text="ok"
        ),
    ]
    for message in samples:
        raw = ServerEnvelope(msg=message).model_dump_json()
        assert ServerEnvelope.model_validate_json(raw).msg == message


def test_contract_key_codes_are_all_representable() -> None:
    for key in ContractKeyCode:
        assert isinstance(key.value, str)
