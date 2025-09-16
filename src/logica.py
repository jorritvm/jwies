
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtSvg import *
import random
from qrc_resource import *

class gui(QWidget):

    def __init__(self, parent=None):
    	###################################
        #eerst laden we de hele gui
        super(gui, self).__init__(parent)
               
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(Qt.darkGreen)
        self.scene.setSceneRect(0,0,600,600)
        self.view = QGraphicsView()
        self.view.setScene(self.scene)
        self.button = QPushButton("KLIK")
        
        self.timer = QTimeLine(1000)
    	self.timer.setCurveShape(QTimeLine.LinearCurve)
        self.animation = QGraphicsItemAnimation();
        self.animation.setTimeLine(self.timer)
        
        self.layout.addWidget(self.view)
        self.layout.addWidget(self.button)
        self.connect(self.button,SIGNAL("clicked()"),self.test)
        
        ###################################
        #dan laden we de logica
        self.bord = bord(self)
    
    def test(self):
        self.timer.start()
    
    def test2(self,x):
        print "framech to "+str(x)
        
    def laadkaarten(self, spelerslijst):
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
        	for kaart in spelerslijst[spelerindex].hand:
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
        		
    def toontroef(self, troefkaart):
    	self.animation.setItem(troefkaart)
    	    	    	
    	self.troefpos = troefkaart.scenePos()
    	x = self.troefpos.x()
    	y = self.troefpos.y()
    	self.animation.setPosAt(0.0,self.troefpos)
    	self.animation.setPosAt(1.0,QPointF(300,300))
    	self.timer.start()
       

class dek():
    #bevat een verzameling 'cards' en een svg renderer voor de cards
    
    def __init__(self, parent=None):
        self.svgrenderer = QSvgRenderer(":/cards.svg")
        self.kaarten = self.maakkaarten()
    
    def maakkaarten(self):
       lijst = list()
       for x in range(52):
           nieuwekaart = kaart(x,self.svgrenderer)
           lijst.append(nieuwekaart)
       return lijst

    def schudkaarten(self):
        tempdek = list()
        for i in range(52):
            tmp = random.choice(self.kaarten)
            self.kaarten.remove(tmp)
            tempdek.append(tmp)
        self.kaarten = tempdek

class kaart(QGraphicsSvgItem):
    #bevat grafische kaart + logica voor kaart
    
    def __init__(self, index, svgrenderer, parent=None):
        super(kaart, self).__init__(parent)
        self.beschrijving = ""
        self.setSharedRenderer(svgrenderer)
        #self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setZValue(index)
        self.index = index
        self.cijfer = index % 13 + 1
    
        if index < 13:
            self.soort = "klaver"
            svgdescription = "_club"
        elif index < 26:
            self.soort = "koeken"
            svgdescription = "_diamond"
        elif index < 39:
            self.soort = "schoppen"
            svgdescription = "_spade"
        elif index < 52:
            self.soort = "harten"
            svgdescription = "_heart"
            
        if self.cijfer < 10:
            self.beschrijving = self.soort + " " + str(self.cijfer+1) + "[" + str(self.index) + "]"
            svgdescription = str(self.cijfer+1)+svgdescription
        elif self.cijfer == 10:
            self.beschrijving = self.soort + " " + "boer" + "[" + str(self.index) + "]"
            svgdescription = "jack"+svgdescription
        elif self.cijfer == 11:    
            self.beschrijving = self.soort + " " + "dame" + "[" + str(self.index) + "]"
            svgdescription = "queen"+svgdescription
        elif self.cijfer == 12:
            self.beschrijving = self.soort + " " + "heer" + "[" + str(self.index) + "]"
            svgdescription = "king"+svgdescription
        elif self.cijfer == 13:
            self.beschrijving = self.soort + " " + "aas" + "[" + str(self.index) + "]"
            svgdescription = "1"+svgdescription
                
        self.setElementId(svgdescription)
    
    def printkaart(self):
        print self.beschrijving
        
    def mousePressEvent(self, event):
    	self.emit(SIGNAL("cardclicked(kaart)"), self)
    	#self.printkaart() #debug
                                     
class bord(QObject):
	def __init__(self,gui):
		self.spelerslijst = [0]*4
		self.actievespelerindex = 1
		self.slag = list()
		self.gui = gui

		self.zetspeler(0,mens("[[speler0]]"))
		self.zetspeler(1,pc("[[speler1]]"))
		self.zetspeler(2,pc("[[speler2]]"))
		self.zetspeler(3,pc("[[speler3]]"))
		
		self.dek = dek()
		for kaart in self.dek.kaarten:
			self.connect(kaart,SIGNAL("cardclicked(kaart)"),self.kaartgeklikt)
		self.deler = 1 #deze index duidt aan welke speler de deler is
		self.startspel()
	
	def kaartgeklikt(self, kaart):
		if self.spelstatus == "troefbekijken":
			if kaart == self.troefkaart:
				self.spelerslijst[0].setkenttroef(True)
				self.startspel2()
				
	def zetspeler(self, index, speler):
		self.spelerslijst[index] = speler

	def startspel(self):
		self.dek.schudkaarten()
		self.verdeelkaarten()
		self.troef = self.dek.kaarten[51].soort
		self.troefkaart = self.dek.kaarten[51]
		self.gui.laadkaarten(self.spelerslijst)
		self.gui.toontroef(self.dek.kaarten[51])
		self.spelstatus = "troefbekijken"
	
	def startspel2(self):
		#we moeten eerst controleren dat alle spelers de troef gezien hebben voor we doorgaan
		x=0
		for speler in self.spelerslijst:
			if speler.kenttroef == True:
				x = x + 1
		if x != 4:
			print "troef niet bij iedereen gekend" 
			return 
		if x == 4:
			print "iedereen kent de troef we spelen voort"
			#we gaan nu vragen wat iedereen wil spelen op basis van zijn kaarten
			for speler in self.spelerslijst:
				pass

	def verdeelkaarten(self):
		i = self.deler
		for speler in self.spelerslijst:
			speler.sethand(self.dek.kaarten[i*13:(i+1)*13])
			i = (i + 1) % 4

	def magopbord(self,kaart,speler):
		if len(self.slag) == 0:
			return True
		else:
			slagsoort = self.slag[0].kaart.soort
			if kaart.soort == slagsoort:
				return True
			elif kaart.soort == self.troef:
				return True
			else:
				return not speler.heeftsoort(slagsoort)
		
			
	def startspel3(self,spelerindex):
		for slagindex in range(13):
			for speler in self.spelerslijst[spelerindex:]+self.spelerslijst[:spelerindex]:
				print speler.naam
				speler.toonkaarten()
			
			for i in range(4):
				speler = self.spelerslijst[spelerindex%4]
				kaart = speler.legkaart()
				if self.magopbord(kaart,speler):
				    gk = gespeeldekaart(speler,kaart)
				    self.slag.append(gk)
				else:
					print "foute kaart"
				spelerindex = spelerindex + 1
				self.toonslag()
			
			winnaar = self.geefwinnaar()
			i = 0
			for speler in self.spelerslijst:
				if speler == winnaar:
					winnaarindex = i
				i += 1
			spelerindex = winnaarindex
			
			self.slag = list()
			
			print "Slag gaat naar: "+winnaar.naam
			
			#whitespace
			print " "
			print " "
			
	
	def toonslag(self):
		print "SLAG SO FAR: ",
		for gk in self.slag:
			print gk.kaart.kaartbeschrijving(),
		print ""
	
	def geefwinnaar(self):
		slagsoort = self.slag[0].kaart.soort
		troef = self.troef
		troefspelers = list()
		slagsoortspelers = list()
		
		#zoek alle troefspelers
		for gk in self.slag:
			if gk.kaart.soort == troef:
				troefspelers.append(gk)
				
	    #zoek alle slagsoortspelers
		for gk in self.slag:
			if gk.kaart.soort == slagsoort:
				slagsoortspelers.append(gk)
		
		if len(troefspelers) == 0:
			#niemand heeft troef gespeeld
			bestespeler = None
			max = -99
			for gk in slagsoortspelers:
				if gk.kaart.cijfer > max:
					bestespeler = gk.speler
					max = gk.kaart.cijfer
			return bestespeler
		else:
			#er hebben mensen troef gespeeld
			bestespeler = None
			max = -99
			for gk in troefspelers:
				if gk.kaart.cijfer > max:
					bestespeler = gk.speler
					max = gk.kaart.cijfer
			return bestespeler
				
	
	
class speler(object): #new style class
	def __init__(self):
		self.naam = ""
		self.hand = list()
		self.kenttroef = False

	def sorteerhand(self):
		#print "sorteerhand"
		#self.toonkaarten()
		p = len(self.hand) 
		while p > 0: #p loops outer loop
			i = 0  #i loops inner loop
			x = -1  #x holds highest card so far
			while i < p:
				if self.hand[i].index > x:
					x = self.hand[i].index
					y = i 
					#print "grootste is "+x
				i += 1
		
			self.hand.insert(p, self.hand[y]) #insert the highest card after p in the deck
			self.hand.remove(self.hand[y]) #and of course remove that card where it used to be
			p -= 1
		
	def sethand(self,hand):
		self.hand = hand
		self.sorteerhand()
	
	def toonkaarten(self):
		kaartenlijst = ""
		for kaart in self.hand:
			kaartenlijst = kaartenlijst+kaart.kaartbeschrijving()+","
		print kaartenlijst[:-1]
	
	def heeftsoort(self,zoeksoort):
		for kaart in self.hand:
			if kaart.soort == zoeksoort:
				return True
		return False	

	def setnaam(self,naam):
		self.naam = naam
	
			
	
class mens(speler):
	def __init__(self,naam):
		super(mens,self).__init__()
		self.setnaam(naam)
	
	def legkaart(self):
		print "Speler "+self.naam+" is nu aan de zet"
		temp = raw_input("Welke kaart wil je spelen:")
		kaartindex = int(temp)
		for kaart in self.hand:
			if kaart.index == kaartindex:
				self.hand.remove(kaart)
				return kaart
		print "ERROR DEZE KAART ZIT NIET OP JOU HAND"

	def setkenttroef(self,status): #met deze methode kan je aangeven of een speler de troef al gezien heeft of niet
		self.kenttroef = status
		if status == True:
			print self.naam + "kent nu de troef"
	
class pc(speler):
	def __init__(self,naam):
		super(pc,self).__init__()
		self.setnaam(naam)
		self.kenttroef = True #een bod kent altijd de troef al
	
	def setkenttroef(self,status):
		pass #mag toch nooit op false gezet worden dus lege def


class gespeeldekaart():
	def __init__(self,speler,kaart):
		self.speler = speler
		self.kaart = kaart

