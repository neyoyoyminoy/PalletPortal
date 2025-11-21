"""
WARNING THIS IS A BROKEN VERSION

this is just a test to display 'welcome' and create a glitch effect like spiderman: into the spiderverse

this version is standalone and runs a glitch text splash screen while syncing both ws2812 led strips over spi0 and spi1
it also supports fullscreen mode and a secret exit combo (ctrl + c + v + enter/return)
it fixes the previous versions error of not centering the welcome text or key press event not working
"""

import sys  #import sys
import random  #for glitch randomness
import string  #for scramble characters
import spidev  #spi driver on jetson
from PyQt5.QtCore import Qt, QTimer  #qt core + timers
from PyQt5.QtGui import QPainter, QColor, QFont  #drawing + fonts
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
        except Exception:
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
        if any(v > 255 or v < 0 for v in (R, G, B)):
            raise ValueError("invalid rgb value")
        if led_num > self.led_count - 1:
            raise ValueError("invalid led index")
        RR = format(R, '08b')
        GG = format(G, '08b')
        BB = format(B, '08b')
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
        self.strip0 = SPItoWS(num_leds, bus=0, device=0)  #pin 19 → spi0_mosi
        self.strip1 = SPItoWS(num_leds, bus=1, device=0)  #pin 37 → spi1_mosi

    def set_all(self, rgb):
        r, g, b = rgb
        for i in range(self.strip0.led_count):
            self.strip0.RGBto3Bytes(i, r, g, b)
            self.strip1.RGBto3Bytes(i, r, g, b)
        self.strip0.LED_show()
        self.strip1.LED_show()

    def off(self):
        try:
            self.strip0.LED_OFF_ALL()
        except Exception:
            pass
        try:
            self.strip1.LED_OFF_ALL()
        except Exception:
            pass


#-------------------- glitch text widget --------------------
class GlitchText(QWidget):
    def __init__(self, text="WELCOME", led_driver=None):
        super().__init__()
        self.text = text  #base text
        self.scrambled = text  #scrambled version
        self.glitch_strength = 0  #glitch strength
        self.led = led_driver  #dual led strips

        self.font = QFont("Arial", 72, QFont.Bold)
        self.setStyleSheet("background-color: black;")

        self.setFocusPolicy(Qt.StrongFocus)  #needed for key input
        self.setFocus()  #force widget to take focus

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_glitch)
        self.timer.start(60)

    def set_led_color(self, rgb):
        if not self.led:
            return
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

        x = (self.width() - text_w) // 2  #center horizontally
        y = (self.height() + text_h) // 2 - fm.descent()  #center vertically

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
                jitter_y = y + random.randint(-20, 20)
                jitter_x = x + random.randint(-10, 10)
                p.setPen(QColor(255, 0, 255, 200))
                p.drawText(jitter_x, jitter_y, self.scrambled)
                self.set_led_color((255, 0, 255))

    def keyPressEvent(self, e):
        self._pressed = getattr(self, "_pressed", set())
        self._pressed.add(e.key())

        if {Qt.Key_Control, Qt.Key_C, Qt.Key_V}.issubset(self._pressed) and \
           (Qt.Key_Enter in self._pressed or Qt.Key_Return in self._pressed):
            QApplication.quit()

    def keyReleaseEvent(self, e):
        self._pressed = getattr(self, "_pressed", set())
        if e.key() in self._pressed:
            self._pressed.remove(e.key())


#-------------------- main window wrapper --------------------
class DemoWindow(QWidget):
    def __init__(self, led_driver=None):
        super().__init__()
        self.setWindowTitle("welcome screen glitch test")
        self.setStyleSheet("background-color: black;")

        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addStretch(1)  #center widget vertically
        self.glitch = GlitchText("WELCOME", led_driver=led_driver)
        layout.addWidget(self.glitch)
        layout.addStretch(1)

        self.setLayout(layout)
        self.showFullScreen()


#-------------------- entry point --------------------
if __name__ == "__main__":
    leds = None
    try:
        leds = DualStripDriver(num_leds=5)
    except Exception as e:
        print(f"led init failed: {e}")
        leds = None

    app = QApplication(sys.argv)
    w = DemoWindow(led_driver=leds)
    w.show()

    if leds is not None:
        app.aboutToQuit.connect(leds.off)

    sys.exit(app.exec_())
