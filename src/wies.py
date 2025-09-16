#!/usr/bin/python
############################################################################
#    Copyright (C) 2014 by Jorrit Vander Mynsbrugge                        #
#    jorrit.vm@gmail.com                                                   #
#                                                                          #
#    This program is free software; you can redistribute it and#or modify  #
#    it under the terms of the GNU General Public License as published by  #
#    the Free Software Foundation; either version 2 of the License, or     #
#    (at your option) any later version.                                   #
#                                                                          #
#    This program is distributed in the hope that it will be useful,       #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of        #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         #
#    GNU General Public License for more details.                          #
#                                                                          #
#    You should have received a copy of the GNU General Public License     #
#    along with this program; if not, write to the                         #
#    Free Software Foundation, Inc.,                                       #
#    59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.             #
############################################################################

import sys
import sysconfig
from green import Green
from PyQt5.Qt import QObject, QApplication

class wies(QObject):
    def __init__(self, parent = None):
        QObject.__init__(self, parent)
        username = input("What is your username? ")
        hj = input("Do you want to host or join a game? ")        
        if hj == "host":
            print("Starting a server...")
            self.server = WiesServer()
        ip = input("To what IP do you want to connect? ")
        print("Connecting graphical client to server...")
        pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = wies()
    main.show()
    sys.exit(app.exec_())