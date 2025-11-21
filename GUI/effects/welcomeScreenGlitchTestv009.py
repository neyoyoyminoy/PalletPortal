import sys
import random
import string
import spidev
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout


# -------------------- WS2812 strip driver --------------------
class SPItoWS:
    def __init__(self, ledc=5, bus=0, device=0):
        self.led_count = ledc
        self.bus = bus
        self.device = device
        self.X = "100" * (self.led_count * 8 * 3)
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


# -------------------- Dual strips (SPI0 + SPI1) --------------------
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


# -------------------- Glitch text widget --------------------
class GlitchText(QWidget):
    def __init__(self, text="WELCOME", led_driver=None):
        super().__init__()
        self.text = text
        self.scrambled = text
        self.glitch_strength = 0
        self.led = led_driver

        self.font = QFont("Sans Serif", 72, QFont.Bold)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_glitch)
        self.timer.start(60)

    def set_led_color(self, rgb):
        if self.led:
            self.led.set_all(rgb)

    def update_glitch(self):
        if random.random() < 0.35:
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

        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.scrambled)
        text_h = fm.height()

        x = (self.width() // 2) - (text_w // 2)
        y = (self.height() // 2) + (text_h // 4)

        # Base white
        p.setPen(QColor(255, 255, 255))
        p.drawText(x, y, self.scrambled)
        self.set_led_color((255, 255, 255))

        if self.glitch_strength > 0:
            shift = self.glitch_strength

            p.setPen(QColor(255, 0, 0, 180))
            p.drawText(x - shift, y, self.scrambled)
            self.set_led_color((255, 0, 0))

            p.setPen(QColor(0, 255, 255, 180))
            p.drawText(x + shift, y, self.scrambled)
            self.set_led_color((0, 255, 255))

            if random.random() < 0.4:
                p.setPen(QColor(255, 0, 255, 200))
                p.drawText(x + random.randint(-10, 10),
                           y + random.randint(-20, 20),
                           self.scrambled)
                self.set_led_color((255, 0, 255))


# -------------------- Main window (fullscreen + exit combo) --------------------
class DemoWindow(QWidget):
    def __init__(self, led_driver=None):
        super().__init__()
        self._pressed = set()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.glitch = GlitchText("WELCOME", led_driver)
        layout.addWidget(self.glitch)

        self.setLayout(layout)

    def keyPressEvent(self, e):
        self._pressed.add(e.key())
        if {Qt.Key_Control, Qt.Key_C, Qt.Key_V}.issubset(self._pressed) and \
           (Qt.Key_Return in self._pressed or Qt.Key_Enter in self._pressed):
            QApplication.quit()

    def keyReleaseEvent(self, e):
        self._pressed.discard(e.key())


# -------------------- Entry point --------------------
if __name__ == "__main__":
    leds = None
    try:
        leds = DualStripDriver(num_leds=5)
    except Exception as e:
        print("LED init failed:", e)

    app = QApplication(sys.argv)
    w = DemoWindow(led_driver=leds)
    w.showFullScreen()

    if leds:
        app.aboutToQuit.connect(leds.off)

    sys.exit(app.exec_())
