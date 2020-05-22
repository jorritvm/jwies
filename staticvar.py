from PyQt5.QtCore import *

SIZEOF_UINT16 = 2
QDATASTREAMVERSION = QDataStream.Qt_5_10

SCENE_RECT_X = 800
SCENE_RECT_Y = 600
CARDSCALE = 0.594

X_CARD = {
    "WEST": 150,
    "NORTH": 335,
    "EAST": 650,
    "SOUTH": 353
}
Y_CARD = {
    "WEST": 160,
    "NORTH": 150,
    "EAST": 440,
    "SOUTH": 450
}
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
    "SOUTH": 435
}
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
CARD_ROTATE = {
    "WEST": 90,
    "NORTH": 180,
    "EAST": 270,
    "SOUTH": 0
}