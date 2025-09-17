from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget
from PyQt5.QtCore import Qt
import sys

# --- Screen 1: Welcome ---
class WelcomeScreen(QWidget):
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

# --- Screen 2: Mode Selection ---
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

# --- Main Window with Key Navigation ---
class MainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.screens = [WelcomeScreen(), ModeScreen()]
        for s in self.screens:
            self.addWidget(s)
        self.setCurrentIndex(0)  # Start on Welcome

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_A:  # left
            self.setCurrentIndex((self.currentIndex() - 1) % self.count())
        elif event.key() == Qt.Key_F:  # right
            self.setCurrentIndex((self.currentIndex() + 1) % self.count())
        elif event.key() == Qt.Key_S:  # select
            self.setCurrentIndex(1)  # Jump to ModeScreen
        elif event.key() ==
