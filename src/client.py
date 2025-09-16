from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtSvg import *
from PyQt5.QtWidgets import *
from resource import *
from server import *

class gui(QWidget):

    def __init__(self, parent=None):
        ###################################
        #eerst laden we de hele gui & toebehoren
        super(gui, self).__init__(parent)
               
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0,0,0,0)
        self.setLayout(self.layout)
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(Qt.darkGreen)
        self.scene.setSceneRect(0,0,600,600)
        self.view = QGraphicsView()
        self.view.setScene(self.scene)
        self.svgrenderer = QSvgRenderer(":/cards.svg")
        self.timer = QTimeLine(1000)
        self.timer.setCurveShape(QTimeLine.LinearCurve)
        self.animation = QGraphicsItemAnimation();
        self.animation.setTimeLine(self.timer)
        self.button = QPushButton("KLIK")
        self.statusbar = QStatusBar()
        self.layout.addWidget(self.view)
        self.layout.addWidget(self.button)
        #self.layout.addWidget(self.statusbar)
        self.connect(self.button,SIGNAL("clicked()"),self.test)
        
        ###################################
        #als join dan laadt je IO, als host dan laadt je serverlogica
        self.bord = bord(self) #in dit geval is onze uitvoerder een host, we impliceren 3 bots
        
    def test(self):
        print("knop geklikt")
    
    def tekennamen(self,namen):
        self.spelersnamen = namen
        self.gspelersnamen = list()
        i = 0
        for naam in namen:
            x = QGraphicsTextItem(QString(naam))
            if i == 0:
                x.setPos(QPointF(175,430))
            elif i == 1:
                x.rotate(90)
                x.setPos(QPointF(170,165))
            elif i == 2:
                x.setPos(QPointF(375,150))
            elif i == 3:
                x.rotate(270)
                x.setPos(QPointF(430,430))
            self.gspelersnamen.append(x)
            self.scene.addItem(x)
            i = i + 1
        
    def laadkaarten(self,indexlijst):
        #eigen kaarten aanmaken
        eigenhand = list()
        for x in indexlijst:
           nieuwekaart = gkaart(x,self.svgrenderer)
           eigenhand.append(nieuwekaart)
           #nieuwekaart.printkaart()

        #rugkaarten aanmaken
        vreemdehanden = list() 
        for y in range(39):
            nieuwekaart = gkaart(52,self.svgrenderer)
            nieuwekaart.setZValue(13+y)
            vreemdehanden.append(nieuwekaart)
        
        self.allehanden = [eigenhand,vreemdehanden[0:13],vreemdehanden[13:26],vreemdehanden[26:39]]
       
        for spelerindex in range(4):
            if spelerindex == 0:
                    x = 160
                    y = 450
            if spelerindex == 1:
                    x = 150
                    y = 160
            if spelerindex == 2:
                    x = 440
                    y = 150
            if spelerindex == 3:
                    x = 450
                    y = 440                                                            

            for kaart in self.allehanden[spelerindex]:
                #kaart.printkaart()
                kaart.scale(0.594,0.594)
                kaart.setPos(x,y)
                #print "bovenstaande kaart staat op "+str(x)+"-"+str(y)
                if spelerindex == 0:
                    x = x + 15
                if spelerindex == 1:
                    kaart.rotate(90)
                    y = y + 15
                if spelerindex == 2:
                    x = x - 15
                    kaart.rotate(180)
                if spelerindex == 3:
                    kaart.rotate(270)
                    y = y - 15
                self.scene.addItem(kaart)
                self.connect(kaart, SIGNAL("gkaartklik(kaart)"),self.geefkaartklikdoor)

    def geefkaartklikdoor(self, kaart):
        x = kaart.index
        self.emit(SIGNAL("kaartgeklikt(int)"), x)
        
    def toontroef(self, troefkaartindex, deler):
        #print "de gui gaat nu troefkaart tonen:"+str(troefkaartindex)
        gezochtekaart = None
        if deler == 0: #je bent zelf deler, de troefkaart zit op je hand
            for kaart in self.allehanden[deler]:
                if kaart.index == troefkaartindex:
                    gezochtekaart = kaart
                    #print "kaart gevonden op je hand"
            if gezochtekaart == None:
                print("ernstige fout, troefkaart zou niet op je hand zitten wat onmogelijk is")
        else:
            #als de deler niet jij bent dan nemen we de eerste kaart van een andere kerel
            gezochtekaart = self.allehanden[deler][0]
        
        #nu tonen we ook de kaart grafisch
        self.animation.setItem(gezochtekaart)
        self.troefpos = gezochtekaart.scenePos()
        x = self.troefpos.x() #(originele locatie)
        y = self.troefpos.y()
        self.animation.setPosAt(0.0,self.troefpos)
        self.animation.setPosAt(1.0,QPointF(300,300))
        self.timer.start()
        #de troef is getoont nu wachten we op de speler die er moet op klikken
        self.troefinfo = [gezochtekaart,x,y]
    
    def verbergtroef(self):
        print("we gaan nu de tref verberge")
        troefkaart = self.troefinfo[0]
        troefkaart.printkaart()
        x = self.troefinfo[1]
        y = self.troefinfo[2]
        print(str(x)+":::"+str(y))
        self.animation.setItem(troefkaart)
        self.troefpos = troefkaart.scenePos()
        self.animation.setPosAt(0.0,QPointF(300,300))
        self.animation.setPosAt(1.0,QPointF(x,y))
        self.timer.start()
        #de troef is weer verborgen
        
    
class gkaart(QGraphicsSvgItem):
    #bevat grafische kaart    
    def __init__(self, index, svgrenderer, parent=None):
        super(gkaart, self).__init__(parent)
        self.setSharedRenderer(svgrenderer)
        self.setZValue(index)
        self.index = index
        self.cijfer = index % 13 + 1
        self.svgdescription = ""
    
        if index < 13:
            self.svgdescription = "_club"
        elif index < 26:
            self.svgdescription = "_diamond"
        elif index < 39:
            self.svgdescription = "_spade"
        elif index < 52:
            self.svgdescription = "_heart"
            
        if self.cijfer < 10:
            self.svgdescription = str(self.cijfer+1)+self.svgdescription
        elif self.cijfer == 10:
            self.svgdescription = "jack"+self.svgdescription
        elif self.cijfer == 11:    
            self.svgdescription = "queen"+self.svgdescription
        elif self.cijfer == 12:
            self.svgdescription = "king"+self.svgdescription
        elif self.cijfer == 13:
            self.svgdescription = "1"+self.svgdescription
        
        if index == 52:
            self.svgdescription = "back"    
        
        self.setElementId(self.svgdescription)
    
    def printkaart(self):
        print(self.svgdescription + "[" + str(self.index) + "]")
        
    def mousePressEvent(self, event):
        self.emit(SIGNAL("gkaartklik(kaart)"), self)
        self.printkaart() #debug

x = gui()