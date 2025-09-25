'''
Brendan Nellis  ujf306
Design 2  Fall 2025

this verison is a iteration of GIUv3 since v4 and v5 used a drop shadow that would break the GUI

this version implements multiple 'dummy' pages
'''

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout
from PyQt5.QtGui import QFont #imports font library
from PyQt5.QtGui import QIcon #lets the GUI have a window icon
from PyQt5.QtCore import Qt #class of 'Qt' is used for alignments

class mainWindow(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle("PalletPortal 1.0")
    self.setGeometry(0, 0, 1024, 600) #x, y, width, height; starting from the top left corner, the display is 1024x600 (7 inch screen)
    
    layout = QVBoxLayout()  #this class is used to construct vertical box layout objects
    title = QLabel("Welcome")
    title.setFont(QFont('Beausite Classic', 40)) #sets font type and size
    title.setStyleSheet("color: #0c2340;"
                        "background-color: #f15a22;"
                        "font-weight: bold;") #this is in hexedecimal although you can put basic color names instead; css like properties; properties should end with ';'
    title.setAlignment(Qt.AlignCenter) #aligns horizontally and vertically center

    subtitle = QLabel("Insert flashdrive to begin")
    subtitle.setFont(QFont('Beausite Classic', 20))
    subtitle.setStyleSheet("color: #0c2340;"
                        "background-color: #f15a22;"
                        "font-weight: bold;")
    subtitle.setAlignment(Qt.AlignCenter)
    
    
    
    layout.addWidget(title)
    layout.addWidget(subtitle)
    self.setLayout(layout)
    self.setCentralWidget(title)
    
    '''
    label.setAlignment(Qt.AlignTop) #aligns vertically to the top
    label.setAlignment(Qt.AlignBottom)  #aligns on the bottom
    label.setAlignment(Qt.AlignVCenter) #aligns vertically center
    label.setAlignment(Qt.AlignRight) #aligns horizontally right
    label.setAlignment(Qt.AlignHCenter) #aligns hoizontally center
    label.setAlignment(Qt.AlignLeft) #aligns horizontally left
    label.setAlignment(Qt.AlignCenter | Qt.AlignTop) #aligns horizontally and vertically center
    '''
    
    '''
    self.ui = Ui_MainWindow()
    self.ui.setupUi(self)
    '''

def main():
  app = QApplication(sys.argv) #sys.argv allows PyQt to pass any command line arguments
  window = mainWindow() #default behavior for a window is to hide it
  window.show() #so this is why '.show' exists so that it can show; but the default behavior will only show it for a split second
  '''
  window.showFullScreen() #this will show the gui in fullscreen
  '''
  sys.exit(app.exec_()) #'app.exec_' method waits for user imput and handles events

if __name__ == "__main__":
  main()
