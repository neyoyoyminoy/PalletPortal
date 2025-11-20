'''
this is just a test to display 'welcome' and create a glitch effect like spiderman: into the spiderverse

this iteration, I incorporated the dual LED strips to be synced with the update_glitch
'''


import sys
import random
import string
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from GUIv27 import SPItoWS   #this is to control the LEDs using my GUI class; both this file and the other have to be in the same location

led = SPItoWS(ledc=5, bus=0, device=0)

class GlitchText(QWidget):
    def __init__(self, text="WELCOME", led_driver=None):
        super().__init__()
        self.text = text  #store text
        self.scrambled = text  #scrambled frame
        self.glitch_strength = 0  #glitch magnitude
        self.led = led_driver  #store led driver for sync

        self.font = QFont("Arial", 72, QFont.Bold)  #big font
        self.setStyleSheet("background-color: black;")  #black bg

        self.timer = QTimer(self)  #glitch frame timer
        self.timer.timeout.connect(self.update_glitch)  #update glitch frames
        self.timer.start(60)  #16 fps

    def set_led_color(self, rgb):
        if not self.led:
            return  #no leds hooked up
        self.led.set_all(rgb)  #set entire strip
        self.led.show()  #push to strip

    def update_glitch(self):
        if random.random() < 0.35:  #glitch trigger chance
            self.glitch_strength = random.randint(3, 12)  #offset amount
            self.scramble()  #scramble chars
        else:
            self.scrambled = self.text  #normal text
            self.glitch_strength = 0  #no glitch

        self.update()  #redraw frame

    def scramble(self):
        chars = list(self.text)  #to list
        for i in range(len(chars)):  #loop chars
            if random.random() < 0.25:  #25% scramble chance
                chars[i] = random.choice(string.ascii_uppercase + string.digits + "!@#$%*")
        self.scrambled = "".join(chars)  #join back

    def paintEvent(self, e):
        p = QPainter(self)  #main painter
        p.setRenderHint(QPainter.TextAntialiasing)  #smooth text
        p.setFont(self.font)  #set font

        fm = self.fontMetrics()  #font measurements
        text_w = fm.horizontalAdvance(self.scrambled)  #text width
        text_h = fm.ascent()  #vertical offset

        x = (self.width() - text_w) // 2  #center x
        y = (self.height() + text_h) // 2  #center y

        # BASE WHITE
        p.setPen(QColor(255, 255, 255))  #white layer
        p.drawText(x, y, self.scrambled)  #draw base
        self.set_led_color((255, 255, 255))  #sync leds

        # GLITCH COLORS
        if self.glitch_strength > 0:
            shift = self.glitch_strength  #how far layers shift

            # RED SHIFT
            p.setPen(QColor(255, 0, 0, 180))
            p.drawText(x - shift, y, self.scrambled)
            self.set_led_color((255, 0, 0))

            # CYAN SHIFT
            p.setPen(QColor(0, 255, 255, 180))
            p.drawText(x + shift, y, self.scrambled)
            self.set_led_color((0, 255, 255))

            # MAGENTA JITTER SLICE
            if random.random() < 0.4:
                jitter_y = y + random.randint(-20, 20)
                jitter_x = x + random.randint(-10, 10)
                p.setPen(QColor(255, 0, 255, 200))
                p.drawText(jitter_x, jitter_y, self.scrambled)
                self.set_led_color((255, 0, 255))

class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("glitch text test")  #window title
        self.setStyleSheet("background-color: black;")  #black bg for whole window

        layout = QVBoxLayout()  #simple layout
        layout.setContentsMargins(0, 0, 0, 0)  #remove padding

        self.glitch = GlitchText("WELCOME", led_driver = led)
        layout.addWidget(self.glitch)  #put in layout

        self.setLayout(layout)  #apply layout
        self.resize(900, 400)  #window size


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DemoWindow()
    w.show()
    sys.exit(app.exec_()) 

