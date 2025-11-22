"""
this is a standalone test for the mode select screen

it has two options:
- ship order
- view order

the highlighted option uses the same glitch colors (cyan, red, magenta)
and all text is size 72
"""

import sys  #import sys
import random  #for glitch randomness
from PyQt5.QtCore import Qt, QTimer, pyqtSignal  #qt core + signals + timer
from PyQt5.QtGui import QPainter, QColor, QFont  #drawing + fonts
from PyQt5.QtWidgets import QApplication, QWidget  #basic widgets


class modeScreen(QWidget):
    shipSelected = pyqtSignal()  #fires when ship order is chosen
    viewOrderSelected = pyqtSignal()  #fires when view order is chosen
    #backToWelcome = pyqtSignal()  #this will be wired in the full gui later

    def __init__(self):
        super().__init__()
        self.setWindowTitle("mode select screen test")  #window title
        self.setStyleSheet("background-color: black;")  #black background
        self.setFocusPolicy(Qt.StrongFocus)  #so keypresses hit this widget

        self.options = ["SHIP ORDER", "VIEW ORDER"]  #menu options
        self.idx = 0  #current selection index (0 = ship, 1 = view)

        self.font = QFont("Arial", 72, QFont.Bold)  #big bold font

        self.scrambled = list(self.options)  #current glitch text per option
        self.glitch_strength = [0, 0]  #per-option glitch strength

        self.timer = QTimer(self)  #timer to drive glitch animation
        self.timer.timeout.connect(self.update_glitch)  #tick handler
        self.timer.start(60)  #about 16 fps

    def update_glitch(self):
        #only glitch the currently selected option
        for i in range(len(self.options)):
            if i == self.idx:
                if random.random() < 0.35:  #chance to trigger glitch
                    self.glitch_strength[i] = random.randint(3, 12)
                    self.scramble_option(i)  #scramble text
                else:
                    self.scrambled[i] = self.options[i]  #back to normal
                    self.glitch_strength[i] = 0
            else:
                self.scrambled[i] = self.options[i]  #keep static
                self.glitch_strength[i] = 0

        self.update()  #request repaint

    def scramble_option(self, i):
        #scramble a single option string
        base = self.options[i]
        chars = list(base)
        for j in range(len(chars)):
            if random.random() < 0.25:  #25% scramble chance per char
                chars[j] = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%*")
        self.scrambled[i] = "".join(chars)

    def paintEvent(self, e):
        p = QPainter(self)  #qt painter
        p.setRenderHint(QPainter.TextAntialiasing)  #smooth text
        p.setFont(self.font)  #set font

        width = self.width()
        height = self.height()

        fm = p.fontMetrics()  #font metrics for layout
        line_h = fm.height()  #line height

        spacing = 30  #vertical spacing between options
        total_h = 2 * line_h + spacing  #total block height
        top_y = (height - total_h) // 2  #top of the two-line block

        #compute baseline positions for each option
        baseline_y0 = top_y + line_h
        baseline_y1 = baseline_y0 + spacing + line_h

        baselines = [baseline_y0, baseline_y1]

        for i, text in enumerate(self.scrambled):
            is_sel = (i == self.idx)  #is this the highlighted option
            base_text = self.options[i]  #non-scrambled text
            y = baselines[i]

            #centered x based on current scrambled text
            text_w = fm.horizontalAdvance(text)
            x = (width - text_w) // 2

            #draw selection background pill
            pad_x = 40  #horizontal padding around text
            pad_y = 10  #vertical padding around text
            rect_w = text_w + pad_x * 2
            rect_h = line_h + pad_y * 2
            rect_x = (width - rect_w) // 2
            rect_y = y - line_h - pad_y + fm.ascent()

            if is_sel:
                p.setBrush(QColor(0, 255, 255, 30))  #soft cyan fill
                p.setPen(QColor(0, 255, 255, 120))  #cyan outline
            else:
                p.setBrush(QColor(255, 255, 255, 5))  #very subtle idle box
                p.setPen(QColor(80, 80, 80, 180))  #dark grey outline

            p.drawRoundedRect(rect_x, rect_y, rect_w, rect_h, 25, 25)  #selection pill

            #base text color
            if is_sel:
                base_color = QColor(255, 255, 255)  #white for selected
            else:
                base_color = QColor(180, 180, 180)  #light grey for idle

            #draw base text
            p.setPen(base_color)
            p.drawText(x, y, text)

            #glitch overlays only for selected option
            if is_sel and self.glitch_strength[i] > 0:
                shift = self.glitch_strength[i]

                #red layer to the left
                p.setPen(QColor(255, 0, 0, 190))
                p.drawText(x - shift, y, text)

                #cyan layer to the right
                p.setPen(QColor(0, 255, 255, 190))
                p.drawText(x + shift, y, text)

                #magenta jitter slice
                if random.random() < 0.4:
                    jitter_x = x + random.randint(-10, 10)
                    jitter_y = y + random.randint(-20, 20)
                    p.setPen(QColor(255, 0, 255, 220))
                    p.drawText(jitter_x, jitter_y, text)

    def _move_down(self):
        #cycle selection down
        self.idx = (self.idx + 1) % len(self.options)  #wrap around
        self.update_glitch()  #immediately refresh glitch state

    def keyPressEvent(self, e):
        key = e.key()

        if key in (Qt.Key_Control, Qt.Key_Return, Qt.Key_Enter):
            self._move_down()  #down selection
            e.accept()
            return

        if key == Qt.Key_V:
            #select current option
            if self.idx == 0:
                self.shipSelected.emit()  #ship option chosen
                print("ship order selected")  #simple debug print
            else:
                self.viewOrderSelected.emit()  #view option chosen
                print("view order selected")  #simple debug print
            e.accept()
            return

        if key == Qt.Key_C:
            #this will go back to the welcome screen in the full gui
            #self.backToWelcome.emit()  #hook this up later
            e.accept()
            return

        super().keyPressEvent(e)


#-------------------- entry --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = modeScreen()
    w.showFullScreen()  #fullscreen window for testing

    sys.exit(app.exec_())
