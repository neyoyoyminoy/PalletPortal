
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget, QPushButton, QTextEdit, QMessageBox
)

BARCODE_FILENAME_CANDIDATES = ["barcodes.txt", "shipment_barcodes.txt"]
REQUIRED_COUNT = 10
REQUIRED_LENGTH = 10

# Common Linux mount roots to scan (Jetson, Ubuntu, etc.)
DEFAULT_MOUNT_ROOTS = [
    "/media",                   # Ubuntu auto-mounts here (e.g., /media/<user>/<label>)
    "/mnt",                     # Generic mounts (/mnt/usb, /mnt/sda1, etc.)
    "/run/media",               # Some distros use this (e.g., /run/media/<user>/<label>)
]

@dataclass
class ShipmentList:
    barcodes: List[str]

    @staticmethod
    def parse(text: str) -> Optional["ShipmentList"]:
        # Accept comma/space/newline separated tokens. Only 10-digit numeric codes count.
        tokens = re.findall(r"\b\d{10}\b", text)
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
        self.filename_candidates = filename_candidates or BARCODE_FILENAME_CANDIDATES
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
            # Walk at depth 2: /media/<user>/<label> or /mnt/usb
            for dirpath, dirnames, filenames in os.walk(root):
                # Light pruning: only search top 2 levels
                depth = dirpath.strip(os.sep).count(os.sep) - root.strip(os.sep).count(os.sep)
                if depth > 2:
                    dirnames[:] = []  # Don't descend further
                    continue

                # Heuristic: removable volumes usually not under system dirs
                if any(p in dirpath for p in ("/proc", "/sys", "/dev", "/run/lock")):
                    continue

                for candidate in self.filename_candidates:
                    full = os.path.join(dirpath, candidate)
                    if os.path.isfile(full):
                        try:
                            text = Path(full).read_text(encoding="utf-8", errors="ignore")
                        except Exception as e:
                            self.status.emit(f"Found {candidate} but couldn't read it: {e}")
                            continue
                        parsed = ShipmentList.parse(text)
                        if parsed:
                            self.validListFound.emit(parsed, dirpath)
                            return
                        else:
                            self.status.emit(f"{candidate} found at {dirpath}, but it didn't contain {REQUIRED_COUNT} unique {REQUIRED_LENGTH}-digit barcodes.")
        self.status.emit("Scanning for USB + barcodes file...")


class WelcomeScreen(QWidget):
    proceed = pyqtSignal(ShipmentList, str)  # (shipment, mount_root)

    def __init__(self):
        super().__init__()
        self.setObjectName("WelcomeScreen")
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
        self.debug.setVisible(False)  # flip to True if you want live logs
        layout.addWidget(self.debug)

        self.manualBtn = QPushButton("Manual Override (Dev Only)")
        self.manualBtn.clicked.connect(self._manual_override)
        self.manualBtn.setVisible(False)  # keep hidden in production
        layout.addWidget(self.manualBtn)

        self.watcher = USBWatcher()
        self.watcher.status.connect(self._on_status)
        self.watcher.validListFound.connect(self._on_valid)
        self.watcher.start()

    def _on_status(self, msg: str):
        self.status.setText(msg)
        if self.debug.isVisible():
            self.debug.append(msg)

    def _on_valid(self, shipment: ShipmentList, mount_root: str):
        self.status.setText("Found valid shipment list. Unlocking...")
        self.watcher.stop()
        self.proceed.emit(shipment, mount_root)

    def _manual_override(self):
        # Dev hook to generate a fake shipment list
        fake = ShipmentList([f"{i:010d}" for i in range(1, REQUIRED_COUNT + 1)])
        self.proceed.emit(fake, "<override>")


class MainScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("MainScreen")
        layout = QVBoxLayout(self)

        title = QLabel("Main / Ship Mode")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 36))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)

        self.info = QLabel("No shipment loaded yet.")
        self.info.setAlignment(Qt.AlignCenter)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

    def load_shipment(self, shipment: ShipmentList, source: str):
        preview = "\n".join(shipment.barcodes)
        self.info.setText(f"Loaded {len(shipment.barcodes)} barcodes from {source}:\n{preview}")


class MainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pallet Portal GUI (USB‑gated)")
        self.setMinimumSize(900, 600)

        self.welcome = WelcomeScreen()
        self.main = MainScreen()

        self.addWidget(self.welcome)  # index 0
        self.addWidget(self.main)     # index 1

        self.setCurrentIndex(0)
        self.welcome.proceed.connect(self._unlock)

    def _unlock(self, shipment: ShipmentList, source: str):
        self.main.load_shipment(shipment, source)
        self.setCurrentIndex(1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
