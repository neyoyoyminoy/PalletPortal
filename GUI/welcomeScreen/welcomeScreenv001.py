"""
this is a glitch welcome screen with additional ui elements:
- top-left project logo
- centered glitching "WELCOME"
- bottom rounded white pill box with "insert flashdrive to begin..."
- fullscreen
- secret exit combo: ctrl + c + v + enter/return
"""

import sys  #import sys
import random  #for glitch randomness
import string  #for scramble characters
import spidev  #spi driver on jetson
from PyQt5.QtCore import Qt, QTimer  #qt core + timers
from PyQt5.QtGui import QPainter, QColor, QFont, QPixmap  #drawing + fonts + images
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout  #basic widgets


#-------------------- ws2812 led strip (spi) --------------------
class SPItoWS:
    def __init__(self, ledc=5, bus=0, device=0):
        self.led_count = ledc  #number of leds in strip
        self.bus = bus  #spi bus index
        self.device = device  #spi device index
        self.X = "100" * (self.led_count * 8 * 3)  #prebuild bit pattern buffer
        self.spi = spidev.SpiDev()  #open spi device
        self.spi.open(bus, device)  #open the selected spi bus/device
        self.spi.max_speed_hz = 2400000  #spi clock
        self.LED_OFF_ALL()  #start with strip off

    def __del__(self):
        try:
            self.spi.close()  #close spi on exit
        except:
            pass

    def _Bytesto3Bytes(self, num, RGB):
        base = num * 24
        for i in range(8):
            pat = "100" if RGB[i] == "0" else "110"
            self.X = self.X[:base + i*3] + pat + self.X[base + i*3 + 3:]

    def LED_show(self):
        Y = []
        for i in range(self.led_count * 9):
            Y.append(int(self.X[i*8:(i+1)*8], 2))
        self.spi.xfer3(Y, 2400000, 0, 8)

    def RGBto3Bytes(self, led_num, R, G, B):
        RR = format(R, "08b")
        GG = format(G, "08b")
        BB = format(B, "08b")
        self._Bytesto3Bytes(led_num * 3, GG)
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


#-------------------- dual strip helper --------------------
class DualStripDriver:
    def __init__(self, num_leds=5):
        self.strip0 = SPItoWS(num_leds, bus=0, device=0)
        self.strip1 = SPItoWS(num_leds, bus=1, device=0)

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


#-------------------- glitch text widget --------------------
class GlitchText(QWidget):
    def __init__(self, text="WELCOME", led_driver=None):
        super().__init__()
        self.text = text  #base text
        self.scrambled = text  #current scrambled text
        self.glitch_strength = 0
        self.led = led_driver

        self.font = QFont("Arial", 72, QFont.Bold)  #glitch font
        self.setStyleSheet("background-color: black;")  #black background

        self.timer = QTimer(self)  #glitch frame timer
        self.timer.timeout.connect(self.update_glitch)
        self.timer.start(60)  #16fps

    def set_led_color(self, rgb):
        if self.led:
            self.led.set_all(rgb)  #sync leds

    def update_glitch(self):
        if random.random() < 0.35:  #chance for glitch
            self.glitch_strength = random.randint(3, 12)
            self.scramble()
        else:
            self.scrambled = self.text
            self.glitch_strength = 0
        self.update()

    def scramble(self):
        chars = list(self.text)
        for i in range(len(chars)):
            if random.random() < 0.25:
                chars[i] = random.choice(string.ascii_uppercase + string.digits + "!@#$%*")
        self.scrambled = "".join(chars)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(self.font)

        widget_rect = self.rect()  #full area
        text_rect = p.boundingRect(widget_rect, Qt.AlignCenter, self.scrambled)

        fm = self.fontMetrics()
        baseline_y = text_rect.y() + text_rect.height() - fm.descent()

        x = text_rect.x()
        y = baseline_y

        # base white
        p.setPen(QColor(255, 255, 255))
        p.drawText(x, y, self.scrambled)
        self.set_led_color((255, 255, 255))

        # glitch layers
        if self.glitch_strength > 0:
            s = self.glitch_strength

            p.setPen(QColor(255, 0, 0, 180))
            p.drawText(x - s, y, self.scrambled)
            self.set_led_color((255, 0, 0))

            p.setPen(QColor(0, 255, 255, 180))
            p.drawText(x + s, y, self.scrambled)
            self.set_led_color((0, 255, 255))

            if random.random() < 0.4:
                p.setPen(QColor(255, 0, 255, 200))
                p.drawText(x + random.randint(-10,10),
                           y + random.randint(-20,20),
                           self.scrambled)
                self.set_led_color((255, 0, 255))


#-------------------- full welcome screen wrapper --------------------
class WelcomeScreen(QWidget):
    def __init__(self, led_driver=None):
        super().__init__()
        self._pressed = set()  #tracks exit combo keys

        self.led_driver = led_driver
        self.logo = QPixmap("/mnt/ssd/PalletPortal/transparentWhiteLogo.png")  #project logo; this is inside the project folder

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.glitch = GlitchText("WELCOME", led_driver)
        layout.addWidget(self.glitch)

        self.setLayout(layout)

    def paintEvent(self, e):
        p = QPainter(self)

        # black background
        p.fillRect(self.rect(), QColor(0, 0, 0))

        # logo top-left
        logo_scaled = self.logo.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        p.drawPixmap(20, 20, logo_scaled)  #offset slightly from edges

        # draw the pill box
        pill_w = 524
        pill_h = 56
        pill_x = (self.width() - pill_w) // 2
        pill_y = self.height() - 140  #position near bottom like your mockup

        p.setBrush(QColor(255, 255, 255))
        p.setPen(QColor(234, 234, 234))
        p.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, 30, 30)

        # pill text
        p.setFont(QFont("Arial", 32))
        p.setPen(QColor(0, 0, 0))
        text = "Insert flashdrive to begin..."
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        tx = pill_x + (pill_w - tw) // 2
        ty = pill_y + (pill_h + th) // 2 - fm.descent()

        p.drawText(tx, ty, text)

    def keyPressEvent(self, e):
        self._pressed.add(e.key())
        if {Qt.Key_Control, Qt.Key_C, Qt.Key_V}.issubset(self._pressed) and \
            (Qt.Key_Enter in self._pressed or Qt.Key_Return in self._pressed):
            QApplication.quit()

    def keyReleaseEvent(self, e):
        self._pressed.discard(e.key())


#-------------------- entry --------------------
if __name__ == "__main__":
    leds = None
    try:
        leds = DualStripDriver(num_leds=5)
    except Exception as e:
        print("led init failed:", e)

    app = QApplication(sys.argv)
    w = WelcomeScreen(led_driver=leds)
    w.showFullScreen()

    if leds:
        app.aboutToQuit.connect(leds.off)

    sys.exit(app.exec_())
