'''
this is just a test to display 'welcome' and create a glitch effect like spiderman: into the spiderverse
'''
import sys  #import sys
import random  #import random
import string  #import string
from PyQt5.QtCore import Qt, QTimer  #pyqt core stuff
from PyQt5.QtGui import QPainter, QColor, QFont  #pyqt drawing and font
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout  #basic pyqt widgets


class GlitchText(QWidget):
    def __init__(self, text="WELCOME"):
        super().__init__()
        self.text = text  #store base text
        self.scrambled = text  #store scrambled frame of text
        self.glitch_strength = 0  #how strong the current glitch frame is

        self.font = QFont("Arial", 72, QFont.Bold)  #set big bold font
        self.setStyleSheet("background-color: black;")  #black background

        self.timer = QTimer(self)  #timer for updating glitch frames
        self.timer.timeout.connect(self.update_glitch)  #connect to update method
        self.timer.start(60)  #roughly 16 fps glitch effect

    def update_glitch(self):
        if random.random() < 0.35:  #random chance for glitch to activate
            self.glitch_strength = random.randint(3, 12)  #random offset amount
            self.scramble()  #scramble characters
        else:
            self.scrambled = self.text  #reset to normal clean text
            self.glitch_strength = 0  #no glitch shift

        self.update()  #trigger repaint

    def scramble(self):
        chars = list(self.text)  #split into list
        for i in range(len(chars)):  #loop chars
            if random.random() < 0.25:  #random chance each char flips
                chars[i] = random.choice(string.ascii_uppercase + string.digits + "!@#$%*")  #pick a glitch char
        self.scrambled = "".join(chars)  #join back together

    def paintEvent(self, e):
        p = QPainter(self)  #main painter
        p.setRenderHint(QPainter.TextAntialiasing)  #smooth text
        p.setFont(self.font)  #apply font

        fm = self.fontMetrics()  #get font metrics
        text_w = fm.horizontalAdvance(self.scrambled)  #width of text
        text_h = fm.ascent()  #height offset

        x = (self.width() - text_w) // 2  #center x
        y = (self.height() + text_h) // 2  #center y

        p.setPen(QColor(255, 255, 255))  #base white text
        p.drawText(x, y, self.scrambled)  #draw main text

        if self.glitch_strength > 0:  #only draw glitch layers if glitch active
            shift = self.glitch_strength  #horizontal split amount

            p.setPen(QColor(255, 0, 0, 180))  #red layer
            p.drawText(x - shift, y, self.scrambled)  #shift left red

            p.setPen(QColor(0, 255, 255, 180))  #cyan layer
            p.drawText(x + shift, y, self.scrambled)  #shift right cyan

            if random.random() < 0.4:  #chance for slice jitter
                jitter_y = y + random.randint(-20, 20)  #random vertical offset
                p.setPen(QColor(255, 0, 255, 200))  #magenta slice
                p.drawText(x + random.randint(-10, 10), jitter_y, self.scrambled)  #offset slice


class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Glitch Text Test")  #window title
        self.setStyleSheet("background-color: black;")  #black bg for whole window

        layout = QVBoxLayout()  #simple layout
        layout.setContentsMargins(0, 0, 0, 0)  #remove padding

        self.glitch = GlitchText("WELCOME")  #add glitch widget
        layout.addWidget(self.glitch)  #put in layout

        self.setLayout(layout)  #apply layout
        self.resize(900, 400)  #window size


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DemoWindow()
    w.show()
    sys.exit(app.exec_()) 

