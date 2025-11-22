"""
this is a pallet portal bouncing logo screen inspired by:
https://github.com/jmsiefer/DVD_Screensaver

changes from original:
- ported from pygame to pyqt5 so it fits into the pallet portal gui stack
- removed audio and fart sounds
- added color cycling between four logo pngs on every wall bounce
- added secret exit combo: hold control + c + v then press enter/return
"""

import sys  #import sys for argv + exit
import random  #random start position + velocity
from PyQt5.QtCore import Qt, QTimer  #qt core + timers
from PyQt5.QtGui import QPainter, QPixmap  #drawing + images
from PyQt5.QtWidgets import QApplication, QWidget  #basic widgets


#paths to the four colored logo pngs in your palletportal folder
LOGO_PATHS = [
    "/mnt/ssd/PalletPortal/transparentWhiteLogo.png",   #white logo
    "/mnt/ssd/PalletPortal/transparentCyanLogo.png",    #cyan logo
    "/mnt/ssd/PalletPortal/transparentRedLogo.png",     #red logo
    "/mnt/ssd/PalletPortal/transparentMagentaLogo.png"  #magenta logo
]


class BouncingLogo(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("pallet portal dvd-style logo")  #window title
        self.setStyleSheet("background-color: black;")  #black background
        self.setFocusPolicy(Qt.StrongFocus)  #make sure keypresses hit this widget

        #load logos once at startup and scale them down to something reasonable
        self.logo_size = 180  #target size for bouncing logo
        self.logos = []  #list of scaled pixmaps
        for path in LOGO_PATHS:
            pm = QPixmap(path)
            if not pm.isNull():
                scaled = pm.scaled(
                    self.logo_size,
                    self.logo_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.logos.append(scaled)

        if not self.logos:
            #fallback tiny blank pixmap if nothing loads (shouldn't happen on jetson)
            self.logos.append(QPixmap(self.logo_size, self.logo_size))

        self.color_index = 0  #which logo index we are showing
        self.current_logo = self.logos[self.color_index]

        #starting position (will be updated once we know window size)
        self.x = 50
        self.y = 50

        #random initial velocity (pixels per frame)
        speed_min = 10.0
        speed_max = 15.0
        self.dx = random.choice([-1, 1]) * random.uniform(speed_min, speed_max)
        self.dy = random.choice([-1, 1]) * random.uniform(speed_min, speed_max)

        self.margin = 2  #soft margin from edges

        self._pressed = set()  #tracks keys for exit combo

        #timer for animation (about 60 fps)
        self.timer = QTimer(self)  #qt timer
        self.timer.timeout.connect(self.update_frame)  #hook to animation step
        self.timer.start(16)  #16 ms ~ 60 fps

    def switch_color(self):
        #advance to next logo color
        self.color_index = (self.color_index + 1) % len(self.logos)
        self.current_logo = self.logos[self.color_index]

    def update_frame(self):
        #update logo position and handle bounces
        w = self.width()
        h = self.height()

        lw = self.current_logo.width()
        lh = self.current_logo.height()

        self.x += self.dx
        self.y += self.dy

        hit_edge = False  #track if we hit any wall this frame

        #left or right wall bounce
        if self.x <= self.margin:
            self.x = self.margin
            self.dx *= -1
            hit_edge = True
        elif self.x + lw >= w - self.margin:
            self.x = w - self.margin - lw
            self.dx *= -1
            hit_edge = True

        #top or bottom wall bounce
        if self.y <= self.margin:
            self.y = self.margin
            self.dy *= -1
            hit_edge = True
        elif self.y + lh >= h - self.margin:
            self.y = h - self.margin - lh
            self.dy *= -1
            hit_edge = True

        if hit_edge:
            self.switch_color()  #change logo color on every bounce

        self.update()  #request repaint

    def paintEvent(self, e):
        #draw the current frame
        p = QPainter(self)  #qt painter
        p.fillRect(self.rect(), Qt.black)  #clear background to black
        p.drawPixmap(int(self.x), int(self.y), self.current_logo)  #draw logo
        p.end()

    def keyPressEvent(self, e):
        k = e.key()
        self._pressed.add(k)  #remember this key is down
        mods = e.modifiers()  #modifier state (control, shift, etc)

        #secret exit combo: hold ctrl + c + v, then press enter/return
        if (mods & Qt.ControlModifier) and \
           (Qt.Key_C in self._pressed) and \
           (Qt.Key_V in self._pressed) and \
           k in (Qt.Key_Return, Qt.Key_Enter):
            QApplication.quit()
            return

        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        #remove released keys from our tracking set
        try:
            self._pressed.remove(e.key())
        except KeyError:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)  #start qt app
    w = BouncingLogo()  #create bouncing logo widget
    w.showFullScreen()  #fullscreen on the 1024x600 display
    sys.exit(app.exec_())  #run event loop
