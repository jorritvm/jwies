from PyQt5.QtCore import *

# DEFINE NETWORK STREAM CONSTANTS
SIZEOF_UINT16 = 2
QDATASTREAMVERSION = QDataStream.Qt_5_10

# DEFINE GRAPHICS SCENE CONSTANTS
SCENE_RECT_X = 800
SCENE_RECT_Y = 600
CARDSCALE = 0.594

# NAME determines position of player name label
X_NAME = {
    "WEST": 10,
    "NORTH": 380,
    "EAST": 650,
    "SOUTH": 380
}
Y_NAME = {
    "WEST": 135,
    "NORTH": 155,
    "EAST": 135,
    "SOUTH": 415
}

# CARD determines position of first card on hand
X_CARD = {
    "WEST": 150,
    "NORTH": 335,
    "EAST": 650,
    "SOUTH": 230
}
Y_CARD = {
    "WEST": 160,
    "NORTH": 150,
    "EAST": 440,
    "SOUTH": 440
}

# INC determines spacing between cards
XINC_CARD = {
    "WEST": 0,
    "NORTH": 20,
    "EAST": 0,
    "SOUTH": 20
}
YINC_CARD = {
    "WEST": 15,
    "NORTH": 0,
    "EAST": -15,
    "SOUTH": 0
}

# ROTATE DETERMINES HOW CARDS ROTATE DEPENDING ON THE SEAT
CARD_ROTATE = {
    "WEST": 90,
    "NORTH": 180,
    "EAST": 270,
    "SOUTH": 0
}

# TRUMPCARD DETERMINES WHERE THE TRUMP CARD IS DRAW DEPENDING ON THE SEAT
X_TRUMPCARD = {
    "WEST": 180,
    "NORTH": 335,
    "EAST": 620,
    "SOUTH": 230
}
Y_TRUMPCARD = {
    "WEST": 160,
    "NORTH": 180,
    "EAST": 440,
    "SOUTH": 410
}

# CARD determines position of first card on hand
X_PLAYED_CARD = {
    "WEST": 400,
    "NORTH": 460,
    "EAST": 340,
    "SOUTH": 320
}
Y_PLAYED_CARD = {
    "WEST": 285,
    "NORTH": 340,
    "EAST": 325,
    "SOUTH": 260
}