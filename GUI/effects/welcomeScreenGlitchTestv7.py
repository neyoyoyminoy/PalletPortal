"""
this is just a test to display 'welcome' and create a glitch effect like spiderman: into the spiderverse

this version fixes the centering on the welcome text
"""

import sys  #import sys
import random  #for glitch randomness
import string  #for scramble characters
import spidev  #spi driver on jetson
from PyQt5.QtCore import Qt, QTimer  #qt core + timers
from PyQt5.QtGui import QPainter, QColor, QFont  #drawing + fonts
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QSizePolicy  #basic widgets + size policy


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
        base = num * 24  #each color byte becomes 24 bits in this encoding
        for i in range(8):
            pat = '100' if RGB[i] == '0' else '110'  #bit encoding for ws2812
            self.X = self.X[:base + i * 3] + pat + self.X[base + i * 3 + 3:]

    def LED_show(self):
        Y = []  #this will hold the encoded bytes
        for i in range(self.led_count * 9):
            Y.append(int(self.X[i * 8:(i + 1) * 8], 2))
        self.spi.xfer3(Y, 2400000, 0, 8)  #send buffer out via spi

    def RGBto3Bytes(self, led_num, R, G, B):
        if any(v > 255 or v < 0 for v in (R, G, B)):
            raise ValueError("invalid rgb value")  #quick sanity check
        if led_num > self.led_count - 1:
            raise ValueError("invalid led index")
        RR = format(R, '08b')  #red byte as bits
        GG = format(G, '08b')  #green byte as bits
        BB = format(B, '08b')  #blue byte as bits
        self._Bytesto3Bytes(led_num * 3, GG)  #ws2812 expects grb order
        self._Bytesto3Bytes(led_num * 3 + 1, RR)
        self._Bytesto3Bytes(led_num * 3 + 2, BB)

    def LED_OFF_ALL(self):
        self.X = "100" * (self.led_count * 8 * 3)  #reset all encoded bits to "off"
        self.LED_show()  #push off frame

    def set_all(self, rgb):
        r, g, b = rgb  #unpack rgb
        for i in range(self.led_count):
            self.RGBto3Bytes(i, r, g, b)  #write same color to each led
        self.LED_show()  #update strip


#-------------------- dual strip helper --------------------
class DualStripDriver:
    def __init__(self, num_leds=5):
        self.strip0 = SPItoWS(num_leds, bus=0, device=0)  #pin 19 -> spi0_mosi
        self.strip1 = SPItoWS(num_leds, bus=1, device=0)  #pin 37 -> spi1_mosi

    def set_all(self, rgb):
        r, g, b = rgb  #unpack rgb
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
        self.scrambled = text  #current scrambled text
        self.glitch_strength = 0  #how strong the current glitch frame is
        self.led = led_driver  #dual strip driver

        self.font = QFont("Arial", 72, QFont.Bold)  #big bold font
        self.setStyleSheet("background-color: black;")  #black background

        # fix: ensure widget expands to full width + height
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  #fix centering issue

        self.timer = QTimer(self)  #timer for driving glitch frames
        self.timer.timeout.connect(self.update_glitch)  #hook to update method
        self.timer.start(60)  #about ~16 fps

    def set_led_color(self, rgb):
        if not self.led:
            return  #no leds provided
        self.led.set_all(rgb)  #push color to both strips

    def update_glitch(self):
        if random.random() < 0.35:  #random chance to enter glitch mode
            self.glitch_strength = random.randint(3, 12)  #horizontal shift in px
            self.scramble()  #scramble characters a bit
        else:
            self.scrambled = self.text  #go back to clean text
            self.glitch_strength = 0  #no shift

        self.update()  #ask qt to repaint

    def scramble(self):
        chars = list(self.text)  #turn string into list for editing
        for i in range(len(chars)):
            if random.random() < 0.25:  #25% of chars get replaced
                chars[i] = random.choice(string.ascii_uppercase + string.digits + "!@#$%*")
        self.scrambled = "".join(chars)  #back to string

    def paintEvent(self, e):
        p = QPainter(self)  #qt painter
        p.setRenderHint(QPainter.TextAntialiasing)  #smooth text edges
        p.setFont(self.font)  #apply font

        fm = self.fontMetrics()  #font metrics
        rect = fm.boundingRect(self.scrambled)  #actual rendered bounds

        text_w = rect.width()  #true width
        text_h = rect.height()  #true height

        cx = self.width() // 2  #midpoint x
        cy = self.height() // 2  #midpoint y

        x = cx - text_w // 2  #center x
        y = cy + text_h // 2 - fm.descent()  #center y baseline fix

        # base white layer
        p.setPen(QColor(255, 255, 255))  #white text
        p.drawText(x, y, self.scrambled)  #draw main text
        self.set_led_color((255, 255, 255))  #leds match base color

        # glitch overlays
        if self.glitch_strength > 0:
            shift = self.glitch_strength  #horizontal displacement

            # red channel shift (left)
            p.setPen(QColor(255, 0, 0, 180))
            p.drawText(x - shift, y, self.scrambled)
            self.set_led_color((255, 0, 0))  #leds flash red with this frame

            # cyan channel shift (right)
            p.setPen(QColor(0, 255, 255, 180))
            p.drawText(x + shift, y, self.scrambled)
            self.set_led_color((0, 255, 255))  #leds flash cyan

            # magenta jitter slice (random vertical offset)
            if random.random() < 0.4:
                jitter_y = y + random.randint(-20, 20)  #small vertical jump
                jitter_x = x + random.randint(-10, 10)  #small horizontal jitter
                p.setPen(QColor(255, 0, 255, 200))
                p.drawText(jitter_x, jitter_y, self.scrambled)
                self.set_led_color((255, 0, 255))  #leds flash magenta


#-------------------- main window wrapper --------------------
class DemoWindow(QWidget):
    def __init__(self, led_driver=None):
        super().__init__()
        self.setWindowTitle("welcome screen glitch test")  #window title
        self.setStyleSheet("background-color: black;")  #black background

        self._pressed = set()  #tracks keys for secret combo

        layout = QVBoxLayout()  #simple vertical layout
        layout.setContentsMargins(0, 0, 0, 0)  #no padding

        # fix: center widget fully inside layout
        layout.setAlignment(Qt.AlignCenter)  #fix centering

        self.glitch = GlitchText("WELCOME", led_driver=led_driver)  #glitch widget
        layout.addWidget(self.glitch)  #fill window

        self.setLayout(layout)  #apply layout

    def keyPressEvent(self, e):
        self._pressed.add(e.key())  #store pressed key

        #check secret combo: ctrl + c + v + enter/return
        if {Qt.Key_Control, Qt.Key_C, Qt.Key_V}.issubset(self._pressed) and \
           (Qt.Key_Enter in self._pressed or Qt.Key_Return in self._pressed):
            QApplication.quit()

    def keyReleaseEvent(self, e):
        if e.key() in self._pressed:
            self._pressed.remove(e.key())  #remove released key


#-------------------- entry point--------------------
if __name__ == "__main__":
    leds = None  #placeholder so we can clean up on exit
    try:
        leds = DualStripDriver(num_leds=5)  #dual ws2812 strips on spi0 + spi1
    except Exception as e:
        print(f"led init failed: {e}")  #basic debug print if spi not ready
        leds = None  #run gui anyway without leds

    app = QApplication(sys.argv)  #start qt app
    w = DemoWindow(led_driver=leds)  #pass leds into glitch window
    w.showFullScreen()  #fullscreen here

    if leds is not None:
        app.aboutToQuit.connect(leds.off)  #make sure strips are cleared on close

    sys.exit(app.exec_())  #qt event loop
