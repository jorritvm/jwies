"""Seat arithmetic.

Seats are absolute indices 0-3 around the table, increasing clockwise (to the
left of the previous seat). Clients translate them to their own point of view;
the engine never deals in relative directions.
"""

from __future__ import annotations

from typing import Final, NewType

__all__ = [
    "ALL_SEATS",
    "FIRST_SEAT",
    "SEAT_COUNT",
    "Seat",
    "left_of",
    "right_of",
    "seat_order_from",
]

Seat = NewType("Seat", int)

SEAT_COUNT: Final = 4
ALL_SEATS: Final[tuple[Seat, ...]] = tuple(Seat(index) for index in range(SEAT_COUNT))
FIRST_SEAT: Final[Seat] = ALL_SEATS[0]


def left_of(seat: Seat, steps: int = 1) -> Seat:
    """The seat ``steps`` places to the left (clockwise) of ``seat``."""
    return Seat((seat + steps) % SEAT_COUNT)


def right_of(seat: Seat, steps: int = 1) -> Seat:
    """The seat ``steps`` places to the right (counter-clockwise) of ``seat``."""
    return Seat((seat - steps) % SEAT_COUNT)


def seat_order_from(first: Seat) -> tuple[Seat, ...]:
    """All four seats starting at ``first`` and moving left."""
    return tuple(left_of(first, step) for step in range(SEAT_COUNT))
