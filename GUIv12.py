'''
this GUI version integrates the dual ping sensors using Joey's functions to avoid crosstalk, it also implements his pillow code structure for a single CSI camera reading barcodes,
and IR USB barcode scanner is also implemented

welcome screen gets bypassed due to testing sake

this is very crude lol
'''

import sys, time, threading, queue, math
from pathlib import Path
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget
import cv2
import Jetson.GPIO as GPIO

# ------------------- CONFIG -------------------
TRIG, ECHO = 23, 24        # your ultrasonic sensor pins (BCM numbering)
DISTANCE_CM_THRESHOLD = 60  # cm threshold to move past welcome
REARM_SECONDS = 2.0         # min time between triggers
CAM_DEVICE = "/dev/video0"  # adjust if needed

# ------------------------------------------------
def gst_pipeline(device, w=640, h=480, fps=30):
    return (
        f"v4l2src device={device} ! "
        f"video/x-raw, width={w}, height={h}, framerate={fps}/1 ! "
        f"videoconvert ! appsink"
    )

SOUND_SPEED = 343.0  # m/s

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    GPIO.output(TRIG, GPIO.LOW)
    time.sleep(0.1)

def ping_once(timeout=0.03):
    GPIO.output(TRIG, GPIO.HIGH)
    time.sleep(10e-6)
    GPIO.output(TRIG, GPIO.LOW)

    t0 = time.time()
    while GPIO.input(ECHO) == 0:
        if time.time() - t0 > timeout:
            return math.inf
    start = time.time()
    while GPIO.input(ECHO) == 1:
        if time.time() - start > timeout:
            return math.inf
    end = time.time()
    dist_cm = ((end - start) * SOUND_SPEED / 2.0) * 100
    return dist_cm

class PingThread(threading.Thread):
    def __init__(self, q: queue.Queue, stop_evt: threading.Event):
        super().__init__(daemon=True)
        self.q = q
        self.stop_evt = stop_evt
        self.last_trigger_ts = 0.0
    def run(self):
        setup_gpio()
        try:
            while not self.stop_evt.is_set():
                d = ping_once()
                if d < DISTANCE_CM_THRESHOLD and (time.time() - self.last_trigger_ts > REARM_SECONDS):
                    self.q.put(("trigger", d))
                    self.last_trigger_ts = time.time()
                time.sleep(0.1)
        finally:
            GPIO.cleanup()

# ------------------- GUI Screens -------------------
class WelcomeScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.title = QLabel("Welcome")
        self.subtitle = QLabel("Stand in front of sensor to begin")
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
        self.option_labels = [QLabel(opt) for opt in self.options]
        for lbl in self.option_labels:
            lbl.setAlignment(Qt.AlignCenter)
        self.title.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addSpacing(16)
        for lbl in self.option_labels:
            layout.addWidget(lbl)
        layout.addStretch(2)
        self.setLayout(layout)
        self._refresh()

    def move_up(self):
        self.index = (self.index - 1) % len(self.options)
        self._refresh()

    def move_down(self):
        self.index = (self.index + 1) % len(self.options)
        self._refresh()

    def _refresh(self):
        for i, lbl in enumerate(self.option_labels):
            if i == self.index:
                lbl.setStyleSheet("font-size: 32px; font-weight: bold; color: #4caf50;")
            else:
                lbl.setStyleSheet("font-size: 28px; color: #888;")

class ShipModeScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.title = QLabel("Ship Mode")
        self.subtitle = QLabel("Camera and scanner active")
        for w in (self.title, self.subtitle):
            w.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 48px; font-weight: 700;")
        self.subtitle.setStyleSheet("font-size: 24px; color: #88a;")
        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addStretch(2)
        self.setLayout(layout)

# ------------------- Main Window -------------------
class MainWindow(QStackedWidget):
    trigger_signal = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.welcome = WelcomeScreen()
        self.select_mode = SelectModeScreen()
        self.ship_mode = ShipModeScreen()
        self.addWidget(self.welcome)
        self.addWidget(self.select_mode)
        self.addWidget(self.ship_mode)
        self.setCurrentIndex(0)

        # ping thread
        self.ev_q = queue.Queue()
        self.stop_evt = threading.Event()
        self.ping_thread = PingThread(self.ev_q, self.stop_evt)
        self.ping_thread.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_events)
        self.timer.start(100)
        self.trigger_signal.connect(self._on_trigger)

        self.cap = None

    def check_events(self):
        while True:
            try:
                kind, val = self.ev_q.get_nowait()
            except queue.Empty:
                break
            if kind == "trigger":
                self.trigger_signal.emit(val)

    def _on_trigger(self, dist):
        if self.currentIndex() == 0:  # welcome
            self.setCurrentIndex(1)

    def keyPressEvent(self, event):
        key = event.key()

        # q = quit
        if key == Qt.Key_Q:
            self.close()
            return

        # c = cancel
        if key == Qt.Key_C:
            if self.currentIndex() == 2:
                self.setCurrentIndex(1)
            elif self.currentIndex() == 1:
                self.setCurrentIndex(0)
            return

        # v = select
        if key == Qt.Key_V:
            if self.currentIndex() == 1:
                if self.select_mode.index == 0:  # Ship Mode
                    self.setCurrentIndex(2)
                    self.start_camera()
                elif self.select_mode.index == 1:  # View Order
                    pass
            return

        # enter = up
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            if self.currentIndex() == 1:
                self.select_mode.move_up()
            return

        # ctrl = down
        if key == Qt.Key_Control:
            if self.currentIndex() == 1:
                self.select_mode.move_down()
            return

    def start_camera(self):
        if self.cap is not None and self.cap.isOpened():
            return
        self.cap = cv2.VideoCapture(gst_pipeline(CAM_DEVICE), cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            self.ship_mode.subtitle.setText("Camera failed to open")
            return
        t = threading.Thread(target=self._camera_loop, daemon=True)
        t.start()

    def _camera_loop(self):
        while self.currentIndex() == 2 and self.cap and self.cap.isOpened():
            ok, frame = self.cap.read()
            if not ok:
                continue
            cv2.imshow("Ship Mode Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cv2.destroyWindow("Ship Mode Camera")

    def closeEvent(self, e):
        self.stop_evt.set()
        try:
            if self.cap and self.cap.isOpened():
                self.cap.release()
        except Exception:
            pass
        cv2.destroyAllWindows()
        super().closeEvent(e)

# ------------------- MAIN -------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.showFullScreen()
    sys.exit(app.exec_())
