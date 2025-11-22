"""
this is a standalone test for the mode select screen v004

it has two options:
- ship order
- view order

the highlighted option uses glitch colors (cyan, red, magenta)
all text is size 72
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
        self.idx = 0  #current selection index

        self.font = QFont("Arial", 72, QFont.Bold)  #big bold font

        self.scrambled = list(self.options)  #current glitch text per option
        self.glitch_strength = [0, 0]  #per-option glitch strength

        self.timer = QTimer(self)  #timer to drive glitch animation
        self.timer.timeout.connect(self.update_glitch)  #tick handler
        self.timer.start(60)  #about 16 fps

        self._pressed = set()  #tracks keys for exit combo

    #-------------------- glitch logic --------------------
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
        base = self.options[i]  #original text
        chars = list(base)  #to list
        for j in range(len(chars)):
            if random.random() < 0.25:  #25% scramble chance
                chars[j] = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%*")
        self.scrambled[i] = "".join(chars)  #back to string

    #-------------------- drawing --------------------
    def paintEvent(self, e):
        p = QPainter(self)  #qt painter
        p.setRenderHint(QPainter.TextAntialiasing)  #smooth text
        p.setFont(self.font)  #set font

        width = self.width()
        height = self.height()

        #fill background
        p.fillRect(self.rect(), QColor(0, 0, 0))  #solid black bg

        fm = p.fontMetrics()  #font metrics
        line_h = fm.height()  #line height

        rect_h = int(line_h * 1.4)  #button height
        spacing = 40  #vertical space between buttons
        total_h = rect_h * 2 + spacing  #total stack height

        top_y = (height - total_h) // 2  #top of first button
        rect_w = int(width * 0.7)  #button width as fraction of screen
        rect_x = (width - rect_w) // 2  #centered x

        for i, text in enumerate(self.scrambled):
            is_sel = (i == self.idx)  #is this the highlighted option
            rect_y = top_y + i * (rect_h + spacing)  #button y

            #selection pill styling
            if is_sel:
                p.setBrush(QColor(0, 40, 40, 230))  #teal-ish fill
                p.setPen(QColor(0, 255, 255, 220))  #cyan outline
            else:
                p.setBrush(QColor(15, 15, 15, 230))  #dark grey fill
                p.setPen(QColor(120, 120, 120, 160))  #soft grey outline

            p.drawRoundedRect(rect_x, rect_y, rect_w, rect_h, 40, 40)  #rounded pill

            #center text inside button
            text_w = fm.horizontalAdvance(text)  #current text width
            baseline_y = rect_y + (rect_h + line_h) // 2 - fm.descent()  #vert center baseline
            x = rect_x + (rect_w - text_w) // 2  #centered x
            y = baseline_y  #baseline y

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

    #-------------------- selection helpers --------------------
    def _move_down(self):
        self.idx = (self.idx + 1) % len(self.options)  #cycle options
        self.update_glitch()  #refresh visual state

    #-------------------- key handling --------------------
    def keyPressEvent(self, e):
        k = e.key()
        self._pressed.add(k)  #track pressed key

        mods = e.modifiers()  #check modifier state

        #secret exit combo: ctrl + c + v + enter/return
        if (mods & Qt.ControlModifier) and \
           (Qt.Key_C in self._pressed) and \
           (Qt.Key_V in self._pressed) and \
           k in (Qt.Key_Return, Qt.Key_Enter):
            QApplication.quit()
            return

        #down selection: control or enter/return
        if k in (Qt.Key_Control, Qt.Key_Return, Qt.Key_Enter):
            self._move_down()
            e.accept()
            return

        #select current option with 'v'
        if k == Qt.Key_V:
            if self.idx == 0:
                self.shipSelected.emit()
                print("ship order selected")  #debug print
            else:
                self.viewOrderSelected.emit()
                print("view order selected")  #debug print
            e.accept()
            return

        #placeholder for going back to welcome with 'c'
        if k == Qt.Key_C:
            #self.backToWelcome.emit()  #wire this in full gui later
            e.accept()
            return

        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        self._pressed.discard(e.key())  #remove released key


#-------------------- entry --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = modeScreen()
    w.showFullScreen()  #fullscreen window for testing

    sys.exit(app.exec_())
