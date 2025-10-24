'''
this doesn't use the ping sensors or USB manifest
'''

import sys, threading, queue, time
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget
import cv2

# ---- Optional IR scanner (HID keyboard) ----
try:
    from evdev import InputDevice, categorize, ecodes
    HAVE_EVDEV = True
except Exception:
    HAVE_EVDEV = False

SCANNER_EVENT_DEV = None  # e.g., "/dev/input/by-id/usb-...-event-kbd"

def scanner_loop(event_dev_path, out_q, stop_evt):
    """Read from HID scanner and send barcodes to queue"""
    if not HAVE_EVDEV or not event_dev_path:
        return
    try:
        dev = InputDevice(event_dev_path)
        buf = []
        for event in dev.read_loop():
            if stop_evt.is_set():
                break
            if event.type == ecodes.EV_KEY and event.value == 1:
                code = event.code
                if code == 28:  # Enter key
                    if buf:
                        out_q.put(("barcode", "".join(buf)))
                        buf = []
                elif 2 <= code <= 11:  # number keys
                    key = str((code - 1) % 10)
                    buf.append(key)
    except Exception as e:
        out_q.put(("scanner_error", str(e)))


# ---- Screens ----
class WelcomeScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.title = QLabel("Welcome")
        self.subtitle = QLabel("Press 'V' to begin")
        for w in (self.title, self.subtitle):
            w.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 56px; font-weight: 700;")
        self.subtitle.setStyleSheet("font-size: 26px; color: #88a;")
        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addStretch(2)
        self.setLayout(layout)


class SelectModeScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.title = QLabel("Select Mode")
        self.options = ["Ship Mode", "View Order"]
        self.index = 0
        self.labels = [QLabel(opt) for opt in self.options]
        for l in self.labels:
            l.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addSpacing(12)
        for l in self.labels:
            layout.addWidget(l)
        layout.addStretch(2)
        self.setLayout(layout)
        self.refresh()

    def move_up(self):
        self.index = (self.index - 1) % len(self.options)
        self.refresh()

    def move_down(self):
        self.index = (self.index + 1) % len(self.options)
        self.refresh()

    def refresh(self):
        for i, lbl in enumerate(self.labels):
            if i == self.index:
                lbl.setStyleSheet("font-size: 32px; font-weight: bold; color: #4caf50;")
            else:
                lbl.setStyleSheet("font-size: 28px; color: #888;")


class ShipModeScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.title = QLabel("Ship Mode")
        self.subtitle = QLabel("Camera and scanner active")
        self.barcode = QLabel("")
        for w in (self.title, self.subtitle, self.barcode):
            w.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 48px; font-weight: 700;")
        self.subtitle.setStyleSheet("font-size: 24px; color: #88a;")
        self.barcode.setStyleSheet("font-size: 30px; color: #4caf50;")
        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(12)
        layout.addWidget(self.barcode)
        layout.addStretch(2)
        self.setLayout(layout)

    def set_barcode(self, text):
        self.barcode.setText(text)


# ---- Main Window ----
class MainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.welcome = WelcomeScreen()
        self.select_mode = SelectModeScreen()
        self.ship_mode = ShipModeScreen()
        self.addWidget(self.welcome)
        self.addWidget(self.select_mode)
        self.addWidget(self.ship_mode)
        self.setCurrentIndex(0)

        self.cap = None
        self.stop_evt = threading.Event()
        self.scanner_thread = None
        self.ev_q = queue.Queue()

        self.timer = self.startTimer(50)

    def timerEvent(self, event):
        while not self.ev_q.empty():
            kind, payload = self.ev_q.get()
            if kind == "barcode":
                self.ship_mode.set_barcode(f"Scanned: {payload}")
            elif kind == "scanner_error":
                self.ship_mode.set_barcode(f"Scanner error: {payload}")

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Q:
            self.close()
            return

        if key == Qt.Key_C:  # Cancel
            if self.currentIndex() == 2:
                self.stop_camera()
                self.setCurrentIndex(1)
            elif self.currentIndex() == 1:
                self.setCurrentIndex(0)
            return

        if key == Qt.Key_V:  # Select
            if self.currentIndex() == 0:
                self.setCurrentIndex(1)
            elif self.currentIndex() == 1:
                if self.select_mode.index == 0:
                    self.setCurrentIndex(2)
                    self.start_camera()
                    self.start_scanner()
                elif self.select_mode.index == 1:
                    pass
            return

        if key in (Qt.Key_Return, Qt.Key_Enter):  # Up
            if self.currentIndex() == 1:
                self.select_mode.move_up()
            return

        if key == Qt.Key_Control:  # Down
            if self.currentIndex() == 1:
                self.select_mode.move_down()
            return

    # --- Camera handling ---
    def start_camera(self):
        if self.cap is not None and self.cap.isOpened():
            return
        self.cap = cv2.VideoCapture("/dev/video0")
        if not self.cap.isOpened():
            self.ship_mode.subtitle.setText("Camera failed to open")
            return
        threading.Thread(target=self.camera_loop, daemon=True).start()

    def camera_loop(self):
        while self.currentIndex() == 2 and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                continue
            cv2.imshow("Ship Mode Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cv2.destroyWindow("Ship Mode Camera")

    def stop_camera(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()

    # --- Scanner handling ---
    def start_scanner(self):
        global SCANNER_EVENT_DEV
        if self.scanner_thread is not None:
            return
        if SCANNER_EVENT_DEV is None and HAVE_EVDEV:
            byid = Path("/dev/input/by-id")
            if byid.exists():
                for p in sorted(byid.iterdir()):
                    if p.name.endswith("event-kbd"):
                        SCANNER_EVENT_DEV = str(p)
                        break
        if HAVE_EVDEV and SCANNER_EVENT_DEV:
            self.stop_evt.clear()
            self.scanner_thread = threading.Thread(
                target=scanner_loop,
                args=(SCANNER_EVENT_DEV, self.ev_q, self.stop_evt),
                daemon=True
            )
            self.scanner_thread.start()
        else:
            self.ship_mode.set_barcode("No scanner detected.")

    def closeEvent(self, e):
        self.stop_evt.set()
        self.stop_camera()
        super().closeEvent(e)


# ---- Run ----
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.showFullScreen()
    sys.exit(app.exec_())
