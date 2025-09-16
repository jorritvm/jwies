'''
Created on 5-jun.-2014

@author: Jorrit
'''
import sys
import sysconfig
from green import Green
from PyQt5.QtWidgets import QApplication

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = Green()
    main.show()
    sys.exit(app.exec_())