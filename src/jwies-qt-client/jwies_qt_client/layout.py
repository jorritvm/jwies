"""Scene geometry for the card table.

Ported verbatim from the pre-refactor ``src/constants.py``: these numbers are
tuned by eye and there is no reason to re-derive them. Only the network
constants that used to live alongside them are gone, since the wire format is
now JSON over websockets.

Directions are relative to the player looking at the screen: SOUTH is always
you, and the client maps absolute seats onto these using ``direction_of``.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "CARDSCALE",
    "CARD_ROTATE",
    "DIRECTIONS",
    "NAME_COLOR_DEFAULT",
    "SCENE_RECT_X",
    "SCENE_RECT_Y",
    "SELECT_ELEVATION",
    "TEAM_COLOR_ATTACKERS",
    "TEAM_COLOR_DEFENDERS",
    "TRUMP_ELEVATION",
    "XINC_CARD",
    "X_CARD",
    "X_NAME",
    "X_PLAYED_CARD",
    "X_TRUMPCARD",
    "YINC_CARD",
    "Y_CARD",
    "Y_NAME",
    "Y_PLAYED_CARD",
    "Y_TRUMPCARD",
    "direction_of",
]

SCENE_RECT_X: Final = 800
SCENE_RECT_Y: Final = 600
CARDSCALE: Final = 0.594

# Vertical offsets (in scene pixels) for lifting cards out of your own hand.
SELECT_ELEVATION: Final = 40  # card selected to be played
TRUMP_ELEVATION: Final = 25  # dealer's own trump card while it is shown

NAME_COLOR_DEFAULT: Final = "white"
TEAM_COLOR_ATTACKERS: Final = "#ffd54a"  # amber
TEAM_COLOR_DEFENDERS: Final = "#7ec8ff"  # light blue

# Seat order as seen from your chair, going clockwise (to your left).
DIRECTIONS: Final = ("SOUTH", "WEST", "NORTH", "EAST")

X_NAME: Final = {"WEST": 10, "NORTH": 380, "EAST": 650, "SOUTH": 380}
Y_NAME: Final = {"WEST": 135, "NORTH": 155, "EAST": 135, "SOUTH": 415}

X_CARD: Final = {"WEST": 150, "NORTH": 335, "EAST": 650, "SOUTH": 230}
Y_CARD: Final = {"WEST": 160, "NORTH": 150, "EAST": 440, "SOUTH": 440}

XINC_CARD: Final = {"WEST": 0, "NORTH": 20, "EAST": 0, "SOUTH": 20}
YINC_CARD: Final = {"WEST": 15, "NORTH": 0, "EAST": -15, "SOUTH": 0}

CARD_ROTATE: Final = {"WEST": 90, "NORTH": 180, "EAST": 270, "SOUTH": 0}

X_TRUMPCARD: Final = {"WEST": 180, "NORTH": 335, "EAST": 620, "SOUTH": 230}
Y_TRUMPCARD: Final = {"WEST": 160, "NORTH": 180, "EAST": 440, "SOUTH": 410}

X_PLAYED_CARD: Final = {"WEST": 400, "NORTH": 460, "EAST": 340, "SOUTH": 320}
Y_PLAYED_CARD: Final = {"WEST": 285, "NORTH": 340, "EAST": 325, "SOUTH": 260}


def direction_of(seat: int, your_seat: int | None) -> str:
    """Map an absolute seat (0-3) to a screen direction.

    Replaces the old SEATWEST/SEATNORTH/SEATEAST messages and the server-side
    ``neighbouring_player_info``: the server now sends absolute seats plus
    ``your_seat`` and each client works out its own point of view.
    """
    if your_seat is None:
        return "SOUTH"
    return DIRECTIONS[(seat - your_seat) % 4]
