'''
Brendan Nellis  ujf306
Design 2  Fall 2025

using pyqt to make a gui for our pallet portal project

'''

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtGui import QFont #imports font library
from PyQt5.QtGui import QIcon #lets the GUI have a window icon
from PyQt5.QtCore import Qt #class of 'Qt' is used for alignments

class mainWindow(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle("PalletPortal 1.0")
    self.setGeomerty(0, 0, 1024, 600) #x, y, width, height; starting from the top left corner, the display is 1024x600 (7 inch screen)
    self.setWindowIcon(QIcon('colorLogo.jpg'))

    label = QLabel("Welcome", self) #main label
    label.setFont(QFont('Beausite Classic', 40)) #sets font type and size
    label.setStyleSheet("color: #0c2340;"
                        "background-color: #f15a22;"
                        "font-weight: bold;"
                        "font-style: italic;"
                        "text-decoration: underline;") #this is in hexedecimal although you can put basic color names instead; css like properties; properties should end with ';'
    '''
    label.setAlignment(Qt.AlignTop) #aligns vertically to the top
    label.setAlignment(Qt.AlignBottom)  #aligns on the bottom
    label.setAlignment(Qt.AlignVCenter) #aligns vertically center
    label.setAlignment(Qt.AlignRight) #aligns horizontally right
    label.setAlignment(Qt.AlignHCenter) #aligns hoizontally center
    label.setAlignment(Qt.AlignLeft) #aligns horizontally left
    label.setAlignment(Qt.AlignCenter | Qt.AlignTop) #aligns horizontally and vertically center
    '''
    label.setAlignment(Qt.AlignCenter) #aligns horizontally and vertically center

    self.setCentralWidget(label)

    '''
    self.ui = Ui_MainWindow()
    self.ui.setupUi(self)
    '''

def main():
  app = QApplication(sys.argv) #sys.argv allows PyQt to pass any command line arguments
  window = mainWindow() #default behavior for a window is to hide it
  window.show() #so this is why '.show' exists so that it can show; but the default behavior will only show it for a split second
  sys.exit(app.exec_()) #'app.exec_' method waits for user imput and handles events

if __name__ == "__main__":
  main()
