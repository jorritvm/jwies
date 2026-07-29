"""Client-side state.

Deliberately a plain dict-shaped store with no rules in it: a snapshot replaces
it wholesale, events nudge it. Kept separate from the widgets so it can be
tested without starting Qt.
"""

from __future__ import annotations

from typing import Any

__all__ = ["ClientState"]


class ClientState:
    """What this client currently believes about the table."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {
            "username": None,
            "lobby": None,
            "lobbies": [],
            "rulesets": [],
            "scorings": [],
            "seats": [],
            "your_seat": None,
            "dealer_seat": None,
            "hand": [],
            "open_hands": {},
            "trick": [],
            "last_trick": None,
            "show_last_trick": False,
            "trump": None,
            "turned_trump": None,
            "contract": None,
            "trick_counts": {"declarers": 0, "defenders": 0},
            "totals": {},
            "prompt": None,
            "pending_seat": None,
            "paused": False,
            "missing": [],
            "round_number": 0,
            "in_game": False,
        }

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def update(self, **changes: Any) -> None:
        self.data.update(changes)

    def apply_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.update(
            lobby=snapshot.get("lobby"),
            seats=snapshot.get("seats") or [],
            your_seat=snapshot.get("your_seat"),
            dealer_seat=snapshot.get("dealer_seat"),
            hand=snapshot.get("your_hand") or [],
            open_hands=snapshot.get("open_hands") or {},
            trick=snapshot.get("current_trick") or [],
            last_trick=snapshot.get("last_trick"),
            trump=snapshot.get("trump"),
            turned_trump=snapshot.get("turned_trump"),
            contract=snapshot.get("contract"),
            trick_counts=snapshot.get("trick_counts") or {"declarers": 0, "defenders": 0},
            totals=snapshot.get("totals") or {},
            prompt=snapshot.get("prompt"),
            pending_seat=snapshot.get("pending_seat"),
            paused=bool(snapshot.get("paused")),
            missing=snapshot.get("missing_players") or [],
            round_number=snapshot.get("round_number") or 0,
            in_game=True,
        )

    def apply_message(self, message: dict[str, Any]) -> None:
        """Fold one server message into the state."""
        kind = message.get("type")

        if kind == "hello_ok":
            self.update(
                username=message.get("username"),
                rulesets=list(message.get("rulesets") or []),
                scorings=list(message.get("scorings") or []),
            )
        elif kind == "lobby_list":
            self.update(lobbies=list(message.get("lobbies") or []))
        elif kind == "lobby_state":
            self.update(lobby=message.get("lobby"))
        elif kind == "game_started":
            self.update(
                seats=message.get("seats") or [],
                your_seat=message.get("your_seat"),
                in_game=True,
            )
        elif kind == "snapshot":
            self.apply_snapshot(message["snapshot"])
        elif kind == "hand_dealt":
            self.update(hand=list(message.get("cards") or []), trick=[], last_trick=None)
        elif kind == "round_started":
            self.update(
                round_number=message.get("round_number", 0),
                dealer_seat=message.get("dealer_seat"),
                contract=None,
                trump=None,
                turned_trump=None,
                trick=[],
                last_trick=None,
                trick_counts={"declarers": 0, "defenders": 0},
            )
        elif kind == "trump_turned":
            self.update(turned_trump=message.get("card"))
        elif kind == "trump_hidden":
            self.update(turned_trump=None)
        elif kind == "contract_established":
            contract = message["contract"]
            self.update(contract=contract, trump=contract.get("trump"))
        elif kind == "card_played":
            trick = [*self["trick"], {"seat": message["seat"], "card": message["card"]}]
            hand = self["hand"]
            if message["seat"] == self["your_seat"] and message["card"] in hand:
                hand = [code for code in hand]
                hand.remove(message["card"])
            self.update(trick=trick, hand=hand)
        elif kind == "trick_completed":
            self.update(
                trick_counts=message.get("trick_counts") or {"declarers": 0, "defenders": 0},
                last_trick=message.get("cards"),
            )
        elif kind == "table_cleared":
            self.update(trick=[])
        elif kind == "prompt":
            self.update(prompt=message.get("prompt"))
        elif kind == "prompt_cleared":
            self.update(prompt=None)
        elif kind == "round_finished":
            self.update(totals=message.get("totals") or {}, prompt=None)
        elif kind == "game_paused":
            self.update(paused=True, missing=list(message.get("missing") or []), prompt=None)
        elif kind == "game_resumed":
            self.update(paused=False, missing=[])
