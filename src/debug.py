from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtSvg import *
import sys

from gamemaster import *
from card import *
from tcpserver import *


class starter(QWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setGeometry(150, 150,200, 100)
		self.setWindowTitle("RUNNING")
		x = gamemaster(self)
		
if __name__ == "__main__":
	app = QApplication(sys.argv)
	main = starter()
	main.show()
	sys.exit(app.exec_())

