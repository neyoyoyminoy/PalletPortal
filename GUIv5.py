'''
Brendan Nellis  ujf306
Design 2  Fall 2025

using pyqt to make a gui for our pallet portal project

'''

from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QGraphicsDropShadowEffect, QWidget, QVBoxLayout
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt

class mainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PalletPortal 1.0")
        self.resize(1024, 600)
        self.move(100, 100)
        self.setWindowIcon(QIcon('colorLogo.jpg'))

        # central widget + layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # welcome label
        label = QLabel("Welcome")
        label.setFont(QFont('Beausite Classic', 40))
        label.setStyleSheet(
            "color: #0c2340;"
            "background-color: #f15a22;"
            "font-weight: bold;"
        )
        label.setAlignment(Qt.AlignCenter)

        # drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(0)
        shadow.setOffset(0, 0)
        shadow.setColor(Qt.white)
        label.setGraphicsEffect(shadow)

        # add to layout (this will center it automatically)
        layout.addWidget(label, alignment=Qt.AlignCenter)


def main():
  app = QApplication(sys.argv) #sys.argv allows PyQt to pass any command line arguments
  window = mainWindow() #default behavior for a window is to hide it
  window.show() #so this is why '.show' exists so that it can show; but the default behavior will only show it for a split second
  sys.exit(app.exec_()) #'app.exec_' method waits for user imput and handles events

if __name__ == "__main__":
  main()
