"""
this is waitScreenv003.py
this is a pallet portal bouncing logo screen inspired by:
https://github.com/jmsiefer/DVD_Screensaver

changes from original:
- ported from pygame to pyqt5 so it fits into the pallet portal gui stack
- removed audio and fart sounds
- added color cycling between four logo pngs on every wall bounce
- leds now match the logo color exactly
- added secret exit combo: hold control + c + v then press enter/return
"""

import sys  #import sys for argv + exit
import random  #random start position + velocity
import spidev  #spi driver for ws2812 strips
from PyQt5.QtCore import Qt, QTimer  #qt core + timers
from PyQt5.QtGui import QPainter, QPixmap  #drawing + images
from PyQt5.QtWidgets import QApplication, QWidget  #basic widgets


#-------------------- ws2812 strip driver (dual spi) --------------------
class SPItoWS:
    def __init__(self, ledc=5, bus=0, device=0):
        self.led_count = ledc  #led count
        self.bus = bus  #spi bus index
        self.device = device  #spi device index
        self.X = "100" * (self.led_count * 8 * 3)  #ws2812 grb bitbuffer
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = 2400000
        self.LED_OFF_ALL()

    def __del__(self):
        try:
            self.spi.close()
        except:
            pass

    def _Bytesto3Bytes(self, num, RGB):
        base = num * 24
        for i in range(8):
            pat = '100' if RGB[i] == '0' else '110'
            self.X = self.X[:base + i * 3] + pat + self.X[base + i * 3 + 3:]

    def LED_show(self):
        Y = []
        for i in range(self.led_count * 9):
            Y.append(int(self.X[i * 8:(i + 1) * 8], 2))
        self.spi.xfer3(Y, 2400000, 0, 8)

    def RGBto3Bytes(self, led_num, R, G, B):
        RR = format(R, '08b')
        GG = format(G, '08b')
        BB = format(B, '08b')
        self._Bytesto3Bytes(led_num * 3, GG)  #grb order
        self._Bytesto3Bytes(led_num * 3 + 1, RR)
        self._Bytesto3Bytes(led_num * 3 + 2, BB)

    def LED_OFF_ALL(self):
        self.X = "100" * (self.led_count * 8 * 3)
        self.LED_show()

    def set_all(self, rgb):
        r, g, b = rgb
        for i in range(self.led_count):
            self.RGBto3Bytes(i, r, g, b)
        self.LED_show()


class DualStripDriver:
    def __init__(self, num_leds=5):
        self.strip0 = SPItoWS(num_leds, bus=0, device=0)  #pin 19
        self.strip1 = SPItoWS(num_leds, bus=1, device=0)  #pin 37

    def set_all(self, rgb):
        r, g, b = rgb
        for i in range(self.strip0.led_count):
            self.strip0.RGBto3Bytes(i, r, g, b)
            self.strip1.RGBto3Bytes(i, r, g, b)
        self.strip0.LED_show()
        self.strip1.LED_show()

    def off(self):
        try: self.strip0.LED_OFF_ALL()
        except: pass
        try: self.strip1.LED_OFF_ALL()
        except: pass


#-------------------- logo paths --------------------
LOGO_PATHS = [
    "/mnt/ssd/PalletPortal/transparentWhiteLogo.png",
    "/mnt/ssd/PalletPortal/transparentCyanLogo.png",
    "/mnt/ssd/PalletPortal/transparentRedLogo.png",
    "/mnt/ssd/PalletPortal/transparentMagentaLogo.png"
]


#matching led colors for each logo index
LED_COLORS = [
    (255, 255, 255),  #white
    (0, 255, 255),    #cyan
    (255, 0, 0),      #red
    (255, 0, 255)     #magenta
]


#-------------------- bouncing logo widget --------------------
class BouncingLogo(QWidget):
    def __init__(self, leds=None):
        super().__init__()

        self.leds = leds  #dual strip driver

        self.setWindowTitle("pallet portal dvd-style logo")
        self.setStyleSheet("background-color: black;")
        self.setFocusPolicy(Qt.StrongFocus)

        #load and scale logos
        self.logo_size = 180
        self.logos = []
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
            self.logos.append(QPixmap(self.logo_size, self.logo_size))

        self.color_index = 0
        self.current_logo = self.logos[self.color_index]

        #set initial led color
        if self.leds:
            self.leds.set_all(LED_COLORS[self.color_index])

        #initial motion
        self.x = 50
        self.y = 50

        speed_min = 2.0
        speed_max = 3.0
        self.dx = random.choice([-1, 1]) * random.uniform(speed_min, speed_max)
        self.dy = random.choice([-1, 1]) * random.uniform(speed_min, speed_max)

        self.margin = 0  #you removed margins

        self._pressed = set()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)  #about 60fps

    def switch_color(self):
        self.color_index = (self.color_index + 1) % len(self.logos)
        self.current_logo = self.logos[self.color_index]

        #update leds to match logo
        if self.leds:
            self.leds.set_all(LED_COLORS[self.color_index])

    def update_frame(self):
        w, h = self.width(), self.height()
        lw = self.current_logo.width()
        lh = self.current_logo.height()

        self.x += self.dx
        self.y += self.dy

        hit_edge = False

        #left & right
        if self.x <= self.margin:
            self.x = self.margin
            self.dx *= -1
            hit_edge = True
        elif self.x + lw >= w - self.margin:
            self.x = w - self.margin - lw
            self.dx *= -1
            hit_edge = True

        #top & bottom
        if self.y <= self.margin:
            self.y = self.margin
            self.dy *= -1
            hit_edge = True
        elif self.y + lh >= h - self.margin:
            self.y = h - self.margin - lh
            self.dy *= -1
            hit_edge = True

        if hit_edge:
            self.switch_color()

        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        p.drawPixmap(int(self.x), int(self.y), self.current_logo)
        p.end()

    def keyPressEvent(self, e):
        k = e.key()
        self._pressed.add(k)
        mods = e.modifiers()

        #secret exit combo
        if (mods & Qt.ControlModifier) and \
           Qt.Key_C in self._pressed and \
           Qt.Key_V in self._pressed and \
           k in (Qt.Key_Return, Qt.Key_Enter):
            QApplication.quit()
            return

        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        try:
            self._pressed.remove(e.key())
        except:
            pass


#-------------------- entry --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    #create led driver
    try:
        leds = DualStripDriver(num_leds=5)
    except Exception as e:
        print("led init failed:", e)
        leds = None

    w = BouncingLogo(leds=leds)
    w.showFullScreen()

    if leds:
        app.aboutToQuit.connect(leds.off)

    sys.exit(app.exec_())
