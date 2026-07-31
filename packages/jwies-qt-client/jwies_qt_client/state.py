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
        """Fold one server message into the state.

        Only these types change anything. Every other message the server sends
        is an announcement - who won the trick, what the contract came out as,
        that the game is paused - and the snapshot that follows it already says
        so. Deriving the same facts a second time here is exactly how two
        clients end up disagreeing.
        """
        kind = message.get("type")

        if kind == "snapshot":
            self.apply_snapshot(message["snapshot"])
        elif kind == "hello_ok":
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
        # The trick on the table. The engine collects a trick the moment it is
        # won, so no snapshot can describe the seconds it stays there to be
        # admired; these three carry the client across that gap.
        elif kind == "card_played":
            hand = self["hand"]
            if message["seat"] == self["your_seat"]:
                hand = [code for code in hand if code != message["card"]]
            self.update(
                trick=[*self["trick"], {"seat": message["seat"], "card": message["card"]}],
                hand=hand,
            )
        elif kind == "trick_completed":
            self.update(
                trick_counts=message.get("trick_counts") or {"declarers": 0, "defenders": 0},
                last_trick=message.get("cards"),
            )
        elif kind == "table_cleared":
            self.update(trick=[])
