
import os
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
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
    barcodes: List[str]

    @staticmethod
    def parse(text: str) -> Optional["ShipmentList"]:
        import re as _re
        tokens = _re.findall(r"\\b\\d{10}\\b", text)
        unique_tokens = []
        seen = set()
        for t in tokens:
            if t not in seen:
                seen.add(t)
                unique_tokens.append(t)
        if len(unique_tokens) != REQUIRED_COUNT:
            return None
        return ShipmentList(barcodes=unique_tokens)


class USBWatcher(QObject):
    validListFound = pyqtSignal(ShipmentList, str)  # (shipment, mount_root)
    status = pyqtSignal(str)

    def __init__(self, mount_roots=None, filename_candidates=None, poll_ms=1000, parent=None):
        super().__init__(parent)
        self.mount_roots = mount_roots or DEFAULT_MOUNT_ROOTS
        self.filename_candidates = [c.lower() for c in (filename_candidates or BARCODE_FILENAME_CANDIDATES)]
        self.timer = QTimer(self)
        self.timer.setInterval(poll_ms)
        self.timer.timeout.connect(self.scan_once)

    def start(self):
        self.scan_once()
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def scan_once(self):
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
    proceed = pyqtSignal(ShipmentList, str)  # (shipment, mount_root)

    def __init__(self):
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
        if event.key() == Qt.Key_R:
            self._on_status("Manual rescan requested.")
            self.watcher.scan_once()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_status(self, msg: str):
        self.status.setText(msg)
        self.debug.append(msg)

    def _on_valid(self, shipment, root):
        self.watcher.stop()
        self.proceed.emit(shipment, root)


class MenuScreen(QWidget):
    shipSelected = pyqtSignal()
    viewOrderSelected = pyqtSignal()

    def __init__(self):
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
        selected_style = "border: 4px solid #0c2340; border-radius: 16px;"
        normal_style = "border: none;"
        self.top.setStyleSheet(selected_style if self.index == 0 else normal_style)
        self.bottom.setStyleSheet(selected_style if self.index == 1 else normal_style)

    def keyPressEvent(self, event):
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
    ready = pyqtSignal(float, int)  # (distance_in_inches, pin_used)
    log = pyqtSignal(str)

    def __init__(self, pins_board: List[int]):
        super().__init__()
        self.pins = [p for p in pins_board if p is not None]
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        if not GPIO_AVAILABLE:
            self.log.emit("GPIO not available; simulating sensor after 1s.")
            time.sleep(1.0)
            self.ready.emit(24.0, -1)
            return

        try:
            GPIO.setmode(GPIO.BOARD)
            for p in self.pins:
                GPIO.setup(p, GPIO.IN)
                try:
                    GPIO.remove_event_detect(p)
                except Exception:
                    pass

            self.log.emit(f"Waiting for pulse on pins (BOARD): {self.pins}")
            # Loop until we capture a valid pulse on any pin
            while not self._stop:
                for p in self.pins:
                    width_us = self._measure_pulse_us(p, timeout_s=1.0)
                    if width_us is None:
                        continue
                    dist_in = width_us / MB1040_US_PER_INCH
                    self.log.emit(f"Pin {p}: pulse {width_us:.1f} us (~{dist_in:.2f} in)")
                    self.log.emit(f"Pin {p}: pulse {width_us:.1f} us (~{dist_in:.2f} in)")
                    # Trigger only if object is within 18 inches or closer
                    if dist_in <= 18:
                        self.ready.emit(dist_in, p)
                        self._cleanup()
                        return

                # brief pause between scans
                time.sleep(0.01)
        except Exception as e:
            self.log.emit(f"PingWorker error: {e!r}")
        finally:
            self._cleanup()

    def _cleanup(self):
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    def _measure_pulse_us(self, pin: int, timeout_s: float = 1.0) -> Optional[float]:
        """Measure high pulse width in microseconds on 'pin'. Returns None on timeout."""
        start = time.time()
        # wait for rising edge
        while GPIO.input(pin) == GPIO.HIGH:
            if time.time() - start > timeout_s:
                return None
        while GPIO.input(pin) == GPIO.LOW:
            if time.time() - start > timeout_s:
                return None
        rise = time.perf_counter()
        while GPIO.input(pin) == GPIO.HIGH:
            if time.time() - start > timeout_s:
                return None
        fall = time.perf_counter()
        width_us = (fall - rise) * 1e6
        return width_us


class ShipScreen(QWidget):
    def __init__(self):
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
        self.log.append(msg)

    def _on_ready(self, dist_in: float, pin: int):
        self.status.setText("CSI cameras are ready to use")
        self._log(f"Ready from pin {pin}, distance ~{dist_in:.2f} in")

    def closeEvent(self, e):
        try:
            if self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(500)
        except Exception:
            pass
        super().closeEvent(e)

class ViewOrderScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("View Order")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 36))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)

# -------------------- Main window --------------------

class MainWindow(QStackedWidget):
    def __init__(self):
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
        self.menu.shipSelected.connect(lambda: self.setCurrentIndex(2))
        self.menu.viewOrderSelected.connect(lambda: self.setCurrentIndex(3))

    def _unlock_to_menu(self, shipment, source):
        self.expected_barcodes = shipment.barcodes
        self.ship_source = source
        self.setCurrentIndex(1)
        self.menu.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
