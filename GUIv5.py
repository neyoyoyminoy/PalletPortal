'''
Brendan Nellis  ujf306
Design 2  Fall 2025

using pyqt to make a gui for our pallet portal project

'''

import sys
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

        # Central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Set background of entire window
        central_widget.setStyleSheet("background-color: #f15a22;")

        # Welcome label styling (no solid box background)
        Qlabel.setStyleSheet(
            "color: #0c2340;"
            "font-weight: bold;"
            "background-color: transparent;")

        # Drop shadow (visible and slightly offset)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)   # make it soft
        shadow.setOffset(3, 3)    # shift slightly down/right
        shadow.setColor(Qt.white)
        label.setGraphicsEffect(shadow)


        # Add to layout so it's centered in the window
        layout.addWidget(label, alignment=Qt.AlignCenter)

def main():
    app = QApplication(sys.argv)
    window = mainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

