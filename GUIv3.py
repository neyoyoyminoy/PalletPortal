'''
Brendan Nellis  ujf306
Design 2  Fall 2025

using pyqt to make a gui for our pallet portal project

'''

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget
from PyQt5.QtCore import Qt

'''welcome screen'''
class welcomeScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        title = QLabel("Welcome")
        subtitle = QLabel("Insert flashdrive to begin")
        title.setAlignment(Qt.AlignCenter)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.setLayout(layout)

'''mode selection screen'''
class ModeScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        title = QLabel("Select Mode")
        ship = QLabel("Ship Mode")
        view = QLabel("View Order")
        title.setAlignment(Qt.AlignCenter)
        ship.setAlignment(Qt.AlignCenter)
        view.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(ship)
        layout.addWidget(view)
        self.setLayout(layout)

'''key navigation'''
class mainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.screens = [WelcomeScreen(), ModeScreen()]
        for s in self.screens:
            self.addWidget(s)
        self.setCurrentIndex(0)  # Start on Welcome

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_A:  # left
            self.setCurrentIndex((self.currentIndex() - 1) % self.count())
        elif key == Qt.Key_F:  # right
            self.setCurrentIndex((self.currentIndex() + 1) % self.count())
        elif key == Qt.Key_S:  # select
            self.setCurrentIndex(1)  # Jump to ModeScreen
        elif key == Qt.Key_D:  # cancel
            self.setCurrentIndex(0)  # Return to Welcome

'''startup'''
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec_())
