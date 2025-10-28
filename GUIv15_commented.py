'''
this is a code that helps improve that latest thing
'''


'''
imports and basic setup — keeping it light
'''
import os
import re
import sys
import time
'''
imports and basic setup — keeping it light
'''
from pathlib import Path
'''
imports and basic setup — keeping it light
'''
from dataclasses import dataclass
'''
imports and basic setup — keeping it light
'''
from typing import List, Optional, Tuple

'''
imports and basic setup — keeping it light
'''
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread #pyqt core signals/timers
'''
imports and basic setup — keeping it light
'''
from PyQt5.QtGui import QFont #fonts/icons stuff
'''
imports and basic setup — keeping it light
'''
from PyQt5.QtWidgets import ( #widgets for the screens
    QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget, QTextEdit
)

# --- GPIO (Jetson) ---
try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

# -------------------- USB / barcodes gate (unchanged core) --------------------

BARCODE_FILENAME_CANDIDATES = ["barcodes.txt", "shipment_barcodes.txt"]
REQUIRED_COUNT = 10
REQUIRED_LENGTH = 10

def guess_mount_roots():
    '''
    this function does the thing we need here
    '''
    roots = set()
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    for base in ["/media", "/mnt", "/run/media"]:
        roots.add(base)
        if user:
            roots.add(os.path.join(base, user))
    roots.add("/media/jetson")
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    mnt = parts[1]
                    fstype = parts[2].lower()
                    if any(fs in fstype for fs in ("vfat", "exfat", "ntfs", "fuseblk")):
                        roots.add(mnt)
    except Exception:
        pass
    return [r for r in sorted(roots) if os.path.exists(r)]

DEFAULT_MOUNT_ROOTS = guess_mount_roots()

@dataclass
class ShipmentList:
    '''
    this is where i set up shipmentlist stuff
    '''
    def __init__(self, barcodes):
        '''
        this function does the thing we need here
        '''
        self.barcodes = barcodes

    @staticmethod
    def parse(text: str):
        '''
        this function does the thing we need here
        '''
        # Remove UTF-8 BOM if present
        if text and text[0] == "\ufeff":
            text = text[1:]

        # Find any 10-digit runs, regardless of separators
#citation: regex pattern is the standard way to grab clean 10-digit chunks, add your link/source here
        tokens = re.findall(r"(?<!\d)\d{10}(?!\d)", text) #this finds clean 10-digit chunks

        # Keep first occurrence order, enforce uniqueness
        seen = set()
        unique_tokens = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                unique_tokens.append(t)

        return ShipmentList(unique_tokens) if len(unique_tokens) == 10 else None


class USBWatcher(QObject):
    '''
    this is where i set up usbwatcher stuff
    '''
    validListFound = pyqtSignal(ShipmentList, str)  # (shipment, mount_root)
    status = pyqtSignal(str)

    def __init__(self, mount_roots=None, filename_candidates=None, poll_ms=1000, parent=None):
        '''
        this function does the thing we need here
        '''
        super().__init__(parent)
        self.mount_roots = mount_roots or DEFAULT_MOUNT_ROOTS
        self.filename_candidates = [c.lower() for c in (filename_candidates or BARCODE_FILENAME_CANDIDATES)]
        self.timer = QTimer(self)
        self.timer.setInterval(poll_ms)
        self.timer.timeout.connect(self.scan_once)

    def start(self):
        '''
        this function does the thing we need here
        '''
        self.scan_once()
        self.timer.start()

    def stop(self):
        '''
        this function does the thing we need here
        '''
        self.timer.stop()

    def scan_once(self):
        '''
        this function does the thing we need here
        '''
        for root in self.mount_roots:
            if not os.path.exists(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                depth = dirpath.strip(os.sep).count(os.sep) - root.strip(os.sep).count(os.sep)
                if depth > 2:
                    dirnames[:] = []
                    continue
                if any(p in dirpath for p in ("/proc", "/sys", "/dev", "/run/lock")):
                    continue
                lower_files = {fn.lower(): fn for fn in filenames}
                for cand_lower in self.filename_candidates:
                    if cand_lower in lower_files:
                        found_name = lower_files[cand_lower]
                        full = os.path.join(dirpath, found_name)
                        try:
                            text = Path(full).read_text(encoding="utf-8", errors="ignore")
                        except Exception as e:
                            self.status.emit(f"Found {found_name} at {dirpath}, but couldn't read it: {e}")
                            continue
                        parsed = ShipmentList.parse(text)
                        if parsed:
                            self.status.emit(f"Valid list found at: {full}")
                            self.validListFound.emit(parsed, dirpath)
                            return
                        else:
                            self.status.emit(f"{found_name} at {dirpath} did not contain exactly {REQUIRED_COUNT} unique {REQUIRED_LENGTH}-digit barcodes.")
        self.status.emit("Scanning for USB + barcodes file...")

# -------------------- Welcome + Menu --------------------

class WelcomeScreen(QWidget):
    '''
    this is where i set up welcomescreen stuff
    '''
    proceed = pyqtSignal(ShipmentList, str)  # (shipment, mount_root)

    def __init__(self):
        '''
        this function does the thing we need here
        '''
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Welcome")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 40))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("Insert flash drive with barcodes file to begin")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.status = QLabel("Waiting for USB...")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.debug = QTextEdit()
        self.debug.setReadOnly(True)
        self.debug.setVisible(True)
        layout.addWidget(self.debug)

        hint = QLabel("Press 'R' to force a rescan. Looking under: " + ", ".join(DEFAULT_MOUNT_ROOTS))
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self.watcher = USBWatcher()
        self.watcher.status.connect(self._on_status)
        self.watcher.validListFound.connect(self._on_valid)
        self.watcher.start()

    def keyPressEvent(self, event):
        '''
        this function does the thing we need here
        '''
        if event.key() == Qt.Key_R:
            self._on_status("Manual rescan requested.")
            self.watcher.scan_once()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_status(self, msg: str):
        '''
        this function does the thing we need here
        '''
        self.status.setText(msg)
        self.debug.append(msg)

    def _on_valid(self, shipment, root):
        '''
        this function does the thing we need here
        '''
        self.watcher.stop()
        self.proceed.emit(shipment, root)


class MenuScreen(QWidget):
    '''
    this is where i set up menuscreen stuff
    '''
    shipSelected = pyqtSignal()
    viewOrderSelected = pyqtSignal()

    def __init__(self):
        '''
        this function does the thing we need here
        '''
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.options = ["Ship", "View Order"]
        self.index = 0

        self.layout = QVBoxLayout(self)
        self.title = QLabel("Menu")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Beausite Classic", 36))
        self.title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        self.layout.addWidget(self.title)

        self.top = QLabel(self.options[0])
        self.bottom = QLabel(self.options[1])
        for lbl in (self.top, self.bottom):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(QFont("Beausite Classic", 32))
            lbl.setMargin(12)
        self.layout.addWidget(self.top)
        self.layout.addWidget(self.bottom)

        self._refresh()

    def _refresh(self):
        '''
        this function does the thing we need here
        '''
        selected_style = "border: 4px solid #0c2340; border-radius: 16px;"
        normal_style = "border: none;"
        self.top.setStyleSheet(selected_style if self.index == 0 else normal_style)
        self.bottom.setStyleSheet(selected_style if self.index == 1 else normal_style)

    def keyPressEvent(self, event):
        '''
        this function does the thing we need here
        '''
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.index = (self.index - 1) % 2
            self._refresh()
            event.accept()
            return
        if key == Qt.Key_Control:
            self.index = (self.index + 1) % 2
            self._refresh()
            event.accept()
            return
        if key == Qt.Key_V:
            if self.index == 0:
                self.shipSelected.emit()
            else:
                self.viewOrderSelected.emit()
            event.accept()
            return
        super().keyPressEvent(event)

# -------------------- Ship screen with ping sensor wait --------------------


# Config: set your BOARD pin numbers here. Use one or two sensors.
PING_PINS_BOARD = [15, 32]   # two sensors
DETECTION_THRESHOLD_IN = 18  # trigger when object ≤ 18 inches away
# MB1040 scale factor (from your code): 147 us per inch
MB1040_US_PER_INCH = 147.0


class PingWorker(QThread):
    '''
    this is where i set up pingworker stuff
    '''
    """
    Crosstalk-safe ultrasonic polling thread.
    - Alternates sensors with long settle time between switching (like jetson_ping_crosstalk).
    - Adds a short quiet period after each read.
    - Averages multiple pulse-width samples, trimming outliers.
    - Emits ready(distance_inches, pin_used) ONLY when distance <= DETECTION_THRESHOLD_IN.
    - Never returns after first reading; loops until stopped.
    """
    ready = pyqtSignal(float, int)  # (distance_in_inches, pin_used)
    log = pyqtSignal(str)

    def __init__(self, pins_board: List[int]):
        '''
        this function does the thing we need here
        '''
        super().__init__()
        self.pins = [p for p in pins_board if p is not None]
        self._stop = False

        # timings chosen to mirror jetson_ping_crosstalk.py behavior
        self.settle_time_s = 3.0   # long settle when switching sensors
        self.quiet_time_s = 0.5    # short quiet between reads
        self.samples = 7           # number of samples to average per read

    def stop(self):
        '''
        this function does the thing we need here
        '''
        self._stop = True

    def run(self):
        '''
        this function does the thing we need here
        '''
        if not GPIO_AVAILABLE:
            self.log.emit("GPIO not available; simulating sensor after 1s.")
            time.sleep(1.0)
            # simulate far distance; will not trigger threshold
            self._emit_log_and_maybe_ready(24.0, -1)
            return

        try:
            GPIO.setmode(GPIO.BOARD)
            for p in self.pins:
                GPIO.setup(p, GPIO.IN)

            self.log.emit(f"Starting ping initialization with crosstalk-safe alternation on pins (BOARD): {self.pins}")
            last_pin = None
            while not self._stop:
                for pin in self.pins:
                    if self._stop:
                        break

                    # Long settle if we switched sensors, to avoid crosstalk (mirrors reference script).
                    if last_pin is None or pin != last_pin:
                        self.log.emit(f"Reading sensor on pin {pin} (settle {self.settle_time_s:.1f}s)...")
                        self._sleep(self.settle_time_s)
                    else:
                        self.log.emit(f"Reading sensor on pin {pin}...")

                    # Perform averaged read
                    dist_in = self._read_distance_in(pin, samples=self.samples)

                    if dist_in is not None:
                        self.log.emit(f"Pin {pin}: {dist_in:.2f} in")
                        self._emit_log_and_maybe_ready(dist_in, pin)
                    else:
                        self.log.emit(f"Pin {pin}: no valid reading (timeout / noise).")

                    last_pin = pin
                    # Quiet time to allow echoes to dissipate before switching sensors
                    self._sleep(self.quiet_time_s)

        except Exception as e:
            self.log.emit(f"PingWorker error: {e!r}")
        finally:
            self._cleanup()

    def _emit_log_and_maybe_ready(self, dist_in: float, pin: int):
        '''
        this function does the thing we need here
        '''
        # Trigger only if within configured threshold
        try:
            threshold = DETECTION_THRESHOLD_IN
        except NameError:
            threshold = 18  # fallback if constant not present
        if dist_in <= threshold:
            self.ready.emit(dist_in, pin)

    def _sleep(self, seconds: float):
        '''
        this function does the thing we need here
        '''
        # cooperative sleep that respects stop flag
        end = time.time() + seconds
        while not self._stop and time.time() < end:
            time.sleep(0.01)

    def _cleanup(self):
        '''
        this function does the thing we need here
        '''
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    # --- Low-level pulse width sampling ---
    def _measure_pw_us(self, pin: int, timeout_s: float = 0.06) -> Optional[float]:
        """
        Measure the pulse width (in microseconds) of one MB1040 echo.
        Returns None on timeout.
        """
        start = time.time()
        # Wait for line to go LOW then HIGH (begin pulse)
        while GPIO.input(pin) == GPIO.HIGH:
            if self._stop or (time.time() - start) > timeout_s:
                return None
        while GPIO.input(pin) == GPIO.LOW:
            if self._stop or (time.time() - start) > timeout_s:
                return None
        rise = time.perf_counter()
        # Wait for pulse to end
        while GPIO.input(pin) == GPIO.HIGH:
            if self._stop or (time.time() - start) > timeout_s:
                return None
        fall = time.perf_counter()
        return (fall - rise) * 1e6  # microseconds

    def _read_distance_in(self, pin: int, samples: int = 7) -> Optional[float]:
        pws = []
        for _ in range(samples):
            if self._stop:
                return None
            pw = self._measure_pw_us(pin)
            if pw is None:
                continue
            dist_in = pw / MB1040_US_PER_INCH  # 147 µs per inch
            if 1.0 <= dist_in <= 300.0:
                pws.append(dist_in)
            time.sleep(0.01)

        if not pws:
            return None

        # Trim outliers similar to statistics.median-based approach
        pws.sort()
        if len(pws) >= 5:
            pws = pws[1:-1]
        return sum(pws) / len(pws)

class ShipScreen(QWidget):
    '''
    this is where i set up shipscreen stuff
    '''
    def __init__(self):
        '''
        this function does the thing we need here
        '''
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Ship")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 36))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)

        self.status = QLabel("Waiting for ping sensor...")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setVisible(True)
        layout.addWidget(self.log)

        pins = list(PING_PINS_BOARD)
        if OPTIONAL_SECOND_PIN is not None:
            pins.append(OPTIONAL_SECOND_PIN)
        self.worker = PingWorker(pins)
        self.worker.log.connect(self._log)
        self.worker.ready.connect(self._on_ready)
        self.worker.start()

    def _log(self, msg: str):
        '''
        this function does the thing we need here
        '''
        self.log.append(msg)

    def _on_ready(self, dist_in: float, pin: int):
        '''
        this function does the thing we need here
        '''
        self.status.setText("CSI cameras are ready to use")
        self._log(f"Ready from pin {pin}, distance ~{dist_in:.2f} in")

    def closeEvent(self, e):
        '''
        this function does the thing we need here
        '''
        try:
            if self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(500)
        except Exception:
            pass
        super().closeEvent(e)

class ViewOrderScreen(QWidget):
    '''
    this is where i set up vieworderscreen stuff
    '''
    def __init__(self):
        '''
        this function does the thing we need here
        '''
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("View Order")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 36))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)

# -------------------- Main window --------------------

class MainWindow(QStackedWidget):
    '''
    this is where i set up mainwindow stuff
    '''
    def __init__(self):
        '''
        this function does the thing we need here
        '''
        super().__init__()
        self.setWindowTitle("Pallet Portal GUI (USB-gated + Menu + Ping)")
        self.setMinimumSize(900, 600)

        self.welcome = WelcomeScreen()
        self.menu = MenuScreen()
        self.ship = ShipScreen()
        self.view = ViewOrderScreen()

        self.addWidget(self.welcome)  # 0
        self.addWidget(self.menu)     # 1
        self.addWidget(self.ship)     # 2
        self.addWidget(self.view)     # 3

        self.setCurrentIndex(0)
        self.welcome.proceed.connect(self._unlock_to_menu)
        self.menu.shipSelected.connect(lambda: self.setCurrentIndex(2)) #jump to ship mode screen
        self.menu.viewOrderSelected.connect(lambda: self.setCurrentIndex(3)) #jump to view order screen

    def _unlock_to_menu(self, shipment, source):
        '''
        this function does the thing we need here
        '''
        self.expected_barcodes = shipment.barcodes
        self.ship_source = source
        self.setCurrentIndex(1)
        self.menu.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv) #qt app boot
    w = MainWindow() #spin up main window
    w.show() #show it
    sys.exit(app.exec_()) #block here until closed