import time
import configparser
import pydealer as pd
import os

from staticvar import *

def load_settings():
    settings = configparser.ConfigParser()
    settings.read(os.path.join("settings", "player.ini"))
    return settings


def assemble_player_message(mtype, mcontent):
    msg = QByteArray()
    stream = QDataStream(msg, QIODevice.WriteOnly)
    stream.setVersion(QDATASTREAMVERSION)
    stream.writeUInt16(0)
    stream.writeQString(mtype)
    stream.writeQString(mcontent)
    stream.device().seek(0)
    stream.writeUInt16(msg.size() - SIZEOF_UINT16)
    return msg


def timestamp_it(s):
    x = "(" + time.strftime("%H:%M:%S") + ") " + s
    return x


def sort_pdstack_on_hand(stack):
    seq = list()
    for card in stack:
        v = 0
        if card.suit == "Diamonds":
            v += 100
        elif card.suit == "Spades":
            v += 200
        elif card.suit == "Hearts":
            v += 300
        if card.value == "Jack":
            v += 11
        elif card.value == "Queen":
            v += 12
        elif card.value == "King":
            v += 13
        elif card.value == "Ace":
            v += 14
        else:
            v += int(card.value)  # 2 - 10
        seq.append(v)
    sorted_indices = sorted(range(len(seq)), key=seq.__getitem__)
    card_list = [stack[i] for i in sorted_indices]
    return_stack = pd.stack.Stack()
    return_stack.insert_list(card_list)
    return return_stack
