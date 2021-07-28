import pydealer as pd


class Player:
    def __init__(self, player_id):
        self.player_id = player_id
        self.name = ""
        self.socket = None
        self.hand = pd.Stack()
        self.next_block_size = 0

    def amount_of_aces_on_hand(self):
        i = 0
        for card in self.hand:
            if card.value == "Ace":
                i += 1
        return i

    def suit_of_my_single_ace(self):
        for card in self.hand:
            if card.value == "Ace":
                return card.suit
        return None

    def has_kh(self):
        i_have_it = False
        for card in self.hand:
            if card.value == "King" and card.suit == "Hearts":
                i_have_it = True
        return i_have_it

    def has_qh(self):
        i_have_it = False
        for card in self.hand:
            if card.value == "Queen" and card.suit == "Hearts":
                i_have_it = True
        return i_have_it

    def remove_card_from_hand(self, abbrev):
        self.hand.get(abbrev)
