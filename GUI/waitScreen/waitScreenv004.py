"""
this is waitScreenv004.py
this is a pallet portal bouncing logo screen inspired by:
https://github.com/jmsiefer/DVD_Screensaver

changes from original:
- ported from pygame to pyqt5 so it fits into the pallet portal gui stack
- removed audio and fart sounds
- added color cycling between four logo pngs on every wall bounce
- leds now stay synced with the logo color
- added rainbow celebration sequence for corner hits
- rainbow sequence uses a counter clockwise led chase (1→2→3→4→5→10→9→8→7→6)
- added secret exit combo: hold ctrl + c + v then press enter/return
"""

import sys  #for argv + exit
import random  #for random start position + speed
import spidev  #for ws2812 spi control
from PyQt5.QtCore import Qt, QTimer  #timers + key modifiers
from PyQt5.QtGui import QPainter, QPixmap  #drawing + images
from PyQt5.QtWidgets import QApplication, QWidget  #basic qt widgets


#-------------------- hue to rgb converter --------------------
def hue_to_rgb(h):
    #this converts a hue angle (0-360) into an rgb tuple 0-255
    h = float(h % 360)
    x = (1 - abs((h / 60) % 2 - 1)) * 255

    if h < 60:
        return (255, int(x), 0)
    if h < 120:
        return (int(x), 255, 0)
    if h < 180:
        return (0, 255, int(x))
    if h < 240:
        return (0, int(x), 255)
    if h < 300:
        return (int(x), 0, 255)
    return (255, 0, int(x))


#-------------------- ws2812 driver --------------------
class SPItoWS:
    def __init__(self, ledc=5, bus=0, device=0):
        self.led_count = ledc
        self.bus = bus
        self.device = device
        self.X = "100" * (ledc * 8 * 3)  #ws2812 grb bitbuffer

        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = 2400000

        self.LED_OFF_ALL()

    def __del__(self):
        try:
            self.spi.close()
        except:
            pass

    def _Bytesto3Bytes(self, num, RGBbits):
        base = num * 24
        for i in range(8):
            pat = '100' if RGBbits[i] == '0' else '110'
            self.X = (
                self.X[: base + i * 3]
                + pat
                + self.X[base + i * 3 + 3 :]
            )

    def LED_show(self):
        Y = []
        for i in range(self.led_count * 9):
            Y.append(int(self.X[i * 8 : (i + 1) * 8], 2))
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


#-------------------- dual strip wrapper --------------------
class DualStripDriver:
    def __init__(self, num_leds=5):
        self.strip0 = SPItoWS(num_leds, bus=0, device=0)  #left strip
        self.strip1 = SPItoWS(num_leds, bus=1, device=0)  #right strip

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
        except:
            pass
        try:
            self.strip1.LED_OFF_ALL()
        except:
            pass


#-------------------- logo file paths --------------------
LOGO_PATHS = [
    "/mnt/ssd/PalletPortal/transparentWhiteLogo.png",
    "/mnt/ssd/PalletPortal/transparentCyanLogo.png",
    "/mnt/ssd/PalletPortal/transparentRedLogo.png",
    "/mnt/ssd/PalletPortal/transparentMagentaLogo.png",
]

LED_COLORS = [
    (255, 255, 255),  #white
    (0, 255, 255),  #cyan
    (255, 0, 0),  #red
    (255, 0, 255),  #magenta
]


#-------------------- bouncing screen --------------------
class BouncingLogo(QWidget):
    def __init__(self, leds=None):
        super().__init__()

        self.leds = leds  #dual strip driver for leds

        self.setWindowTitle("pallet portal dvd screen")
        self.setStyleSheet("background-color: black;")
        self.setFocusPolicy(Qt.StrongFocus)

        #load + scale logos
        self.logo_size = 180
        self.logos = []
        for p in LOGO_PATHS:
            pm = QPixmap(p)
            if not pm.isNull():
                self.logos.append(
                    pm.scaled(
                        self.logo_size,
                        self.logo_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )

        if not self.logos:
            self.logos.append(QPixmap(self.logo_size, self.logo_size))

        self.color_index = 0
        self.current_logo = self.logos[self.color_index]

        if self.leds:
            self.leds.set_all(LED_COLORS[self.color_index])

        #initial position
        self.x = 50
        self.y = 50

        #slower motion per your tweak
        vmin, vmax = 2.0, 3.0
        self.dx = random.choice([-1, 1]) * random.uniform(vmin, vmax)
        self.dy = random.choice([-1, 1]) * random.uniform(vmin, vmax)

        self.margin = 0  #you disabled margins

        #rainbow celebration settings
        self.celebrating = False
        self.celebrate_step = 0
        self.celebrate_timer = QTimer(self)
        self.celebrate_timer.timeout.connect(self._celebrate_frame)

        #exit combo key tracking
        self._pressed = set()

        #main animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

    #----- rainbow celebration frame -----
    def _celebrate_frame(self):
        #order of leds for ccw cycle (0-based)
        order = [0, 1, 2, 3, 4, 9, 8, 7, 6, 5]

        hue = (self.celebrate_step * 25) % 360
        r, g, b = hue_to_rgb(hue)

        #build a 10-led pattern (1 active pixel)
        pattern = [(0, 0, 0)] * 10
        active = order[self.celebrate_step % len(order)]
        pattern[active] = (r, g, b)

        #map to strips
        if self.leds:
            #left strip handles leds 0-4
            for i in range(5):
                rr, gg, bb = pattern[i]
                self.leds.strip0.RGBto3Bytes(i, rr, gg, bb)

            #right strip handles leds 5-9 mapped to 0-4
            for i in range(5):
                rr, gg, bb = pattern[5 + i]
                self.leds.strip1.RGBto3Bytes(i, rr, gg, bb)

            self.leds.strip0.LED_show()
            self.leds.strip1.LED_show()

        self.celebrate_step += 1

        #stop celebration after ~40 frames
        if self.celebrate_step >= 40:
            self.celebrate_timer.stop()
            self.celebrating = False

    #----- normal color switch -----
    def switch_color(self):
        self.color_index = (self.color_index + 1) % len(self.logos)
        self.current_logo = self.logos[self.color_index]

        if self.leds:
            self.leds.set_all(LED_COLORS[self.color_index])

    #----- main animation update -----
    def update_frame(self):
        w, h = self.width(), self.height()
        lw, lh = self.current_logo.width(), self.current_logo.height()

        self.x += self.dx
        self.y += self.dy

        #individual wall hits
        hit_left = (self.x <= self.margin)
        hit_right = (self.x + lw >= w - self.margin)
        hit_top = (self.y <= self.margin)
        hit_bottom = (self.y + lh >= h - self.margin)

        #handle bouncing
        hit_edge = False

        if hit_left:
            self.x = self.margin
            self.dx *= -1
            hit_edge = True
        elif hit_right:
            self.x = w - lw - self.margin
            self.dx *= -1
            hit_edge = True

        if hit_top:
            self.y = self.margin
            self.dy *= -1
            hit_edge = True
        elif hit_bottom:
            self.y = h - lh - self.margin
            self.dy *= -1
            hit_edge = True

        #corner detection
        corner_hit = (
            (hit_left and hit_top)
            or (hit_left and hit_bottom)
            or (hit_right and hit_top)
            or (hit_right and hit_bottom)
        )

        #corner celebration
        if corner_hit:
            self.celebrating = True
            self.celebrate_step = 0
            self.celebrate_timer.start(50)  #20 fps
            #after celebration, logo color resumes normally
        elif hit_edge and not self.celebrating:
            self.switch_color()

        self.update()

    #----- drawing -----
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        p.drawPixmap(int(self.x), int(self.y), self.current_logo)
        p.end()

    #----- key events -----
    def keyPressEvent(self, e):
        k = e.key()
        self._pressed.add(k)
        mods = e.modifiers()

        #exit combo
        if (
            (mods & Qt.ControlModifier)
            and Qt.Key_C in self._pressed
            and Qt.Key_V in self._pressed
            and k in (Qt.Key_Return, Qt.Key_Enter)
        ):
            QApplication.quit()
            return

        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        try:
            self._pressed.remove(e.key())
        except:
            pass


#-------------------- entry point --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    try:
        leds = DualStripDriver(num_leds=5)
    except Exception as e:
        print("failed to init leds:", e)
        leds = None

    w = BouncingLogo(leds=leds)
    w.showFullScreen()

    if leds:
        app.aboutToQuit.connect(leds.off)

    sys.exit(app.exec_())
