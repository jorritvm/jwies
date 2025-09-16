#class description:
#the gamemaster leads the game, as if he was a 5th person at the table

from card import *
from tcpserver import *

class gamemaster(object):
	
	def __init__(self,parent=None):
		self.parent = parent
		self.deck = list()
		self.create_new_deck()
		
		self.tcps = None
		self.create_tcpserver()
		
		print "einde constructor"
	
	def create_new_deck(self):
		for i in range(52):
			self.deck.append(card(i))
			
	def create_tcpserver(self):
		self.tcps = tcpserver(self.parent) #no parent given to the tcp server
		IP = self.get_ip()
		PORT = self.get_port()
		print str(PORT)
		print type(PORT)
		if not self.tcps.listen(QHostAddress("0.0.0.0"), 9999):
			print "Failed to start server: " + self.tcps.errorString()
			#QMessageBox.critical(self, "TCPSERVER", QString("Failed to start server: %1").arg(self.tcps.errorString()))
			return
		print "server draait"

	def get_ip(self):
		IP = "192.168.0.131"
		return IP	
	
	def get_port(self):
		PORT = 9999
		return PORT
	