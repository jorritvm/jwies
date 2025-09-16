from PyQt5.QtWidgets import QWidget, QLabel, QGridLayout, QGraphicsScene
from PyQt5.Qt import QGraphicsView, QPushButton, QSizePolicy, QGraphicsSvgItem, QSvgRenderer
from PyQt5.QtCore import Qt
from PyQt5 import QtOpenGL
from resource import *

class Green(QWidget):

    def __init__(self, parent = None):
        QWidget.__init__(self, parent) 
        
        #create the base layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0,0,0,0)
        self.setLayout(self.layout)
        
        #create the scene
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(Qt.darkGreen)
        self.scene.setSceneRect(0,0,600,600)
        
        #create a view for the scene
        self.view = QGraphicsView()
        self.view.setScene(self.scene)
        self.view.setMinimumSize(600+2,600+2)
        self.view.setViewport(QtOpenGL.QGLWidget())
        
        #create a debug button
        self.button = QPushButton("KLIK")
        
        #get it together
        self.layout.addWidget(self.view)
        self.layout.addWidget(self.button)
        
        #create an SVGRenderer for the cards in the resource file
        self.svgrenderer = QSvgRenderer(":/cards.svg")

        #connect some signals
        self.button.clicked.connect(self.test)

    def test(self):
        self.newGameInit("jorrit", ["alfa","beta","gamma"],[1,2,3,4,5,6,7,8,9,10,11,12,13])
       
    def newGameInit(self, name, otherplayernames, cards):
        # draw our players cards & those of other players (face down)
        
        # create a list of graphical cards for the real player (south)
        self.playercards_south = list()
        for i in cards:
            self.playercards_south.append(GCard(i, self.svgrenderer))
        # draw these on the scene
        x = 160
        y = 450
        for card in self.playercards_south:             
            card.setScale(0.594)
            card.setPos(x,y)
            x = x + 15
            self.scene.addItem(card)
            
        # create 3 lists of graphical cards (backsides) for the three other players
        self.playercards_east = list()
        for i in range(13):
            self.playercards_east.append(GCard(52, self.svgrenderer))
        self.playercards_north = list()
        for i in range(13):
            self.playercards_north.append(GCard(52, self.svgrenderer))
        self.playercards_west = list()
        for i in range(13):
            self.playercards_west.append(GCard(52, self.svgrenderer))      
 
        # draw them on the scene
        x = 150
        y = 160
        for card in self.playercards_east:                
            card.setScale(0.594)
            card.setPos(x,y)
            card.setRotation(90)
            y = y + 15
            self.scene.addItem(card)    
            
        x = 440
        y = 150
        for card in self.playercards_north:               
            card.setScale(0.594)
            card.setPos(x,y)
            card.setRotation(180)
            x = x - 15
            self.scene.addItem(card)   
                 
        x = 450
        y = 440 
        for card in self.playercards_west:                
            card.setScale(0.594)
            card.setPos(x,y)
            card.setRotation(270)
            y = y - 15
            self.scene.addItem(card)
        
    def playCard(self,index):                
        pass
                                         
class GCard(QGraphicsSvgItem):
   
    def __init__(self, index, svgrenderer, parent=None):
        QGraphicsSvgItem.__init__(self, parent)
        
        self.nr = index % 13 + 1
    
        if index < 13:
            svgdescription = "_club"
        elif index < 26:
            svgdescription = "_diamond"
        elif index < 39:
            svgdescription = "_spade"
        elif index < 52:
            svgdescription = "_heart"
        elif index == 52:
            svgdescription = "back"
            
        if self.nr < 10:
            svgdescription = str(self.nr+1)+svgdescription
        elif self.nr == 10:
            svgdescription = "jack"+svgdescription
        elif self.nr == 11:    
            svgdescription = "queen"+svgdescription
        elif self.nr == 12:
            svgdescription = "king"+svgdescription
        elif self.nr == 13:
            svgdescription = "1"+svgdescription
            
        if index == 52:
            svgdescription = "back"
                
        self.setElementId(svgdescription)
        self.svgdescription = svgdescription
        self.index = index
        self.setSharedRenderer(svgrenderer)
        self.setZValue(index) # to make sure they overlap nicely from the start
        
    #def mousePressEvent(self, event):
    #    self.emit(SIGNAL("cardclicked(kaart)"), self)
        