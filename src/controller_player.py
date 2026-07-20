import pydealer as pd
from PyQt6.QtNetwork import QTcpSocket


class Player:
    def __init__(self, player_id: int) -> None:
        self.player_id = player_id
        self.name = ""
        self.socket: QTcpSocket | None = None
        self.hand = pd.Stack()
        self.next_block_size = 0

    def amount_of_aces_on_hand(self) -> int:
        i = 0
        for card in self.hand:
            if card.value == "Ace":
                i += 1
        return i

    def suit_of_my_single_ace(self) -> str | None:
        for card in self.hand:
            if card.value == "Ace":
                return card.suit
        return None

    def has_kh(self) -> bool:
        i_have_it = False
        for card in self.hand:
            if card.value == "King" and card.suit == "Hearts":
                i_have_it = True
        return i_have_it

    def has_qh(self) -> bool:
        i_have_it = False
        for card in self.hand:
            if card.value == "Queen" and card.suit == "Hearts":
                i_have_it = True
        return i_have_it

    def remove_card_from_hand(self, abbrev: str) -> None:
        self.hand.get(abbrev)
