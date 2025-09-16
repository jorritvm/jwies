from PyQt4.QtCore import *
import random

class bord(QObject):
    def __init__(self,gui):
        self.spelerslijst = [0]*4
        #self.actievespelerindex = 1
        #self.slag = list()
        
        #momenteel verplichten we de logica om met 1 persoon en 3 bots te werken 
        self.zetspeler(0,mens("[[speler0]]"))
        self.zetspeler(1,bot("[[speler1]]"))
        self.zetspeler(2,bot("[[speler2]]"))
        self.zetspeler(3,bot("[[speler3]]"))
        self.spelerslijst[0].setio(gui) #we linken de gui aan de speler
        
        #hier moeten we ale IO's hun signals connecten met de logica
        self.connect(gui, SIGNAL("kaartgeklikt(int)"), self.verwerksignalen)
        
        for speler in self.spelerslijst:
            speler.geefspelernamen(["[[speler0]]","[[speler1]]","[[speler2]]","[[speler3]]"])
        
        self.dek = dek()
        self.deler = 0 #deze index duidt aan welke speler de deler is (index in spelerlijst)
        self.startspel()
              
    
    def zetspeler(self, index, speler):
        self.spelerslijst[index] = speler
        
    def startspel(self):
        self.dek.schudkaarten()
        self.verdeelkaarten()
        self.troef = self.dek.kaarten[51].soort
        self.troefkaart = self.dek.kaarten[51]
        #nu moet je de echte users hun kaarten sturen
        for speler in self.spelerslijst:
            speler.updategui()
        for speler in self.spelerslijst:
            speler.toontroef(self.troefkaart,self.deler)
        self.spelstatus = "troefbekijken"
    
    def startspel2(self):
        #eerst kijken we of alle spelers de troef kennen
        i = 0
        for speler in self.spelerslijst:
            if speler.kenttroef == True:
                i = i + 1
        if i != 4:
            print("niet iedereen kent troef")
        else: 
            print("iedereen kent troef")
            #nu mag de troefkaart weer verdwijnen
            self.spelerslijst[0].io.verbergtroef()
    
    def verdeelkaarten(self):
        #momenteel krijgt de deler de laatste 13 kaarten van de boek, geen 445 deling, elke ronde kaarten randomized
        i = self.deler
        for speler in self.spelerslijst:
            i = (i - 1) % 4
            speler.sethand(self.dek.kaarten[i*13:(i+1)*13])
        
    def verwerksignalen(self,gekliktekaartindex):
        if self.spelstatus == "troefbekijken":
            if gekliktekaartindex == self.troefkaart.index:
                print "de geklikte kaart is de troefkaart"
                self.spelerslijst[0].kenttroef = True
                self.startspel2()
                return
        
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
        self.hand = hand #hand = list() van kaartobjecten
        self.sorteerhand()
    
    def toonkaarten(self): #print je handkaarten
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
    
    def setkenttroef(self,status): #abstract
        pass 
    
    def setio(self,io): #abstract
        pass
    
    def geefspelernamen(self, namen): #abstract
        pass
    
    def updategui(self): #abstract
        pass

    def toontroef(self,troef,deler):
        pass
    
class mens(speler):
    def __init__(self,naam):
        super(mens,self).__init__()
        self.setnaam(naam)
        self.type = "mens"
    
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
    
    def setio(self,io):
        self.io = io #in ons geval nu momenteel nog gewoon de gui
    
    def geefspelernamen(self,namen):
        self.io.tekennamen(namen)
    
    def updategui(self):
        #de speler kan de gui enkel informeren van zijn eigen kaarten, want die van andere spelerobjecten ken hij niet
        indexlijst = list()
        for kaart in self.hand:
            indexlijst.append(kaart.index)
        self.io.laadkaarten(indexlijst)        
    
    def toontroef(self,troefkaart,deler):
        self.io.toontroef(troefkaart.index, deler)
        
class bot(speler):
    def __init__(self,naam):
        super(bot,self).__init__()
        self.setnaam(naam)
        self.type = "bot"
        self.troefkaart = None
        
    def toontroef(self,troefkaart,deler):
        #een bot wordt op deze manier geinformeerd van welke speler welke troefkaart toonde na deling
        self.troefkaart = troefkaart
        self.deler = deler    
        self.kenttroef = True

class dek(object):
    #bevat backend van een boek kaarten    
    def __init__(self, parent=None):
        self.kaarten = self.maakkaarten()
    
    def maakkaarten(self):
       lijst = list()
       for x in range(52):
           nieuwekaart = kaart(x)
           lijst.append(nieuwekaart)
       return lijst

    def schudkaarten(self):
        tempdek = list()
        for i in range(52):
            tmp = random.choice(self.kaarten)
            self.kaarten.remove(tmp)
            tempdek.append(tmp)
        self.kaarten = tempdek

class kaart(object):
    #bevat backend kaart
    def __init__(self, index):
        self.beschrijving = ""
        self.index = index
        self.cijfer = index % 13 + 1
    
        if index < 13:
            self.soort = "klaver"
        elif index < 26:
            self.soort = "koeken"
        elif index < 39:
            self.soort = "schoppen"
        elif index < 52:
            self.soort = "harten"
        if self.cijfer < 10:
            self.beschrijving = self.soort + " " + str(self.cijfer+1) + "[" + str(self.index) + "]"
        elif self.cijfer == 10:
            self.beschrijving = self.soort + " " + "boer" + "[" + str(self.index) + "]"
        elif self.cijfer == 11:    
            self.beschrijving = self.soort + " " + "dame" + "[" + str(self.index) + "]"
        elif self.cijfer == 12:
            self.beschrijving = self.soort + " " + "heer" + "[" + str(self.index) + "]"
        elif self.cijfer == 13:
            self.beschrijving = self.soort + " " + "aas" + "[" + str(self.index) + "]"
                
    def printkaart(self):
        print self.beschrijving
    