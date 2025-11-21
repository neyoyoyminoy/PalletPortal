import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

'''screens'''
class WelcomeScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        title = QLabel("Welcome")
        title.setFont(QFont('Beausite Classic', 40))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Insert flashdrive to begin")
        subtitle.setFont(QFont('Beausite Classic', 20))
        subtitle.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        subtitle.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.setLayout(layout)

class selectModeScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        title = QLabel("Select Mode")
        title.setFont(QFont('Beausite Classic', 40))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Ship Mode | View Order")
        subtitle.setFont(QFont('Beausite Classic', 20))
        subtitle.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        self.setLayout(layout)

class shipModeScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        title = QLabel("Ship Mode")
        title.setFont(QFont('Beausite Classic', 40))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Progress Bar (coming soon)")
        subtitle.setFont(QFont('Beausite Classic', 20))
        subtitle.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        self.setLayout(layout)

class endScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        title = QLabel("Shipment Loaded")
        title.setFont(QFont('Beausite Classic', 40))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("End of Process")
        subtitle.setFont(QFont('Beausite Classic', 20))
        subtitle.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        self.setLayout(layout)


'''main window with stacked screens'''
class MainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PalletPortal 1.0")
        self.setGeometry(0, 0, 1024, 600)

        # Add screens to stack
        self.screens = [WelcomeScreen(), selectModeScreen(), shipModeScreen(), endScreen()]
        for screen in self.screens:
            self.addWidget(screen)

        self.currentIndex = 0
        self.setCurrentIndex(self.currentIndex)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        # Right keys: go forward
        if key in [Qt.Key_V, Qt.Key_Return, Qt.Key_Enter]:
            self.nextScreen()

        # Left keys: go backward
        if key in [Qt.Key_C, Qt.Key_Control]:
            self.previousScreen()

    def nextScreen(self):
        if self.currentIndex < len(self.screens) - 1:
            self.currentIndex += 1
            self.setCurrentIndex(self.currentIndex)

    def previousScreen(self):
        if self.currentIndex > 0:
            self.currentIndex -= 1
            self.setCurrentIndex(self.currentIndex)


'''GUI setup'''
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
