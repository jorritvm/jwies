#class description:
#this is a multithreaded tcp server that can read & write on all its sockets
from PyQt4.QtNetwork import *
from PyQt4.QtCore import *
from PyQt4.QtGui import *

class tcpserver(QTcpServer):

	def __init__(self, parent=None):
		super(tcpserver, self).__init__(parent)
		self.socks = list()

	def incomingConnection(self, socketId):
		print "inc connection triggered"
		t = thread(socketId, self)

		#the socket thread is deleted when run() is finished
		self.connect(t, SIGNAL("finished()"), t, SLOT("deleteLater()"))

		self.connect(t, SIGNAL("messagereceived"), self.process_incomming_msg)
		self.socks.append(t)
		t.start()
		t.send_reply(QString("ID"),QString("Identify please"))
	
	def process_incomming_msg(self,tup):
		typ = str(tup[0])
		if typ == "CHAT":
			#if the incomming msg is a chat message we broadcast it to all other sockets
			self.broadcast(tup)
		if typ == "THROWCARD":
			pass
			
		
	def broadcast(self, tup):
		print "starting broadcast"
		for t in self.socks:
			t.send_reply(tup)
			
	def test(self):
		self.broadcast("BROADCAST TEST")

	
		
class thread(QThread):
	def __init__(self, socketId, parent=None):
		super(thread, self).__init__(parent)
		self.socketId = socketId
        
	def run(self):
		self.socket = QTcpSocket()
		self.socket.setSocketDescriptor(self.socketId)

		#as long as the socket lives, we stay in run()
		while self.socket.state() == QAbstractSocket.ConnectedState:
			NBS = 0

			#exchanged data is binary, so we use a qdatastream
			stream = QDataStream(self.socket)
			stream.setVersion(QDataStream.Qt_4_2)

			#this is a seperate thread which makes using blocking IO OK
			while True:
				#wait forever
				self.socket.waitForReadyRead(-1)
				#two bytes is the size of an unsigned 16 bit integer
				if self.socket.bytesAvailable() >= 2:
					NBS = stream.readUInt16()
					break
					
			#as long as the entire msg isn't received yet, we keep reading
			if self.socket.bytesAvailable() < NBS:
				while True:
					self.socket.waitForReadyRead(-1)
					if self.socket.bytesAvailable() >= NBS:
						break

			#the entire msg is received, now we process them into 2 qstrings
			typ = QString()
			msg = QString()
			tup = (typ,msg)
			stream >> typ >> msg
			self.emit(SIGNAL("messagereceived"), tup) #don't use brackets for the signal, this way we can send a tuple as an argument
            
	def send_reply(self, tup):
		#the msg we are sending is a tuple consisting of 2 QStrings
		print "server stuurt iets"
		reply = QByteArray()
		stream = QDataStream(reply, QIODevice.WriteOnly)
		stream.setVersion(QDataStream.Qt_4_2)
		stream.writeUInt16(0)
		stream << tup[0] << tup[1]
		stream.device().seek(0)
		stream.writeUInt16(reply.size() - 2)
		x = self.socket.write(reply)
		#print "x:"+str(x)

if __name__ == "__main__":
	app = QApplication(sys.argv)
	main = server()
	main.show()
	sys.exit(app.exec_())