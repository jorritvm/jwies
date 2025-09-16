
class card(object):

	def __init__(self,index):
		self.index = index
		self.figure = 0
		self.suit = ""
		self.description = ""
		
		self.set_figure()
		self.set_suit()
		self.set_description()
		
	def set_figure(self):
		self.figure = self.index % 13 + 1

	def set_suit(self):
		if self.index < 13:
			self.suit = "clubs"
		elif self.index < 26:
			self.suit = "diamonds"
		elif self.index < 39:
			self.suit = "spades"
		elif self.index < 52:
			self.suit = "hearts"
				
	def set_description(self):            
		if self.figure < 10:
			self.description = str(self.figure+1) + " of " + self.suit
		elif self.figure == 10:
			self.description = "jack" + " of " + self.suit
		elif self.figure == 11:    
			self.description = "queen" + " of " + self.suit
		elif self.figure == 12:
			self.description = "king" + " of " + self.suit
		elif self.figure == 13:
			self.description = "ace" + " of " + self.suit
			
	def print_description(self):
		print str(self.index)+"-"+self.description