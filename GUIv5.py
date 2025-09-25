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

        # Welcome label
        label = QLabel("Welcome")
        label.setFont(QFont('Beausite Classic', 40))
        label.setStyleSheet(
            "color: #0c2340;"
            "background-color: #f15a22;"
            "font-weight: bold;"
        )
        label.setAlignment(Qt.AlignCenter)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(0)
        shadow.setOffset(0, 0)  # keeps shadow centered
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

