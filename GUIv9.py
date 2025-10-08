
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Set

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget, QTextEdit
)

BARCODE_FILENAME_CANDIDATES = ["barcodes.txt", "shipment_barcodes.txt"]
REQUIRED_COUNT = 10
REQUIRED_LENGTH = 10

def guess_mount_roots() -> List[str]:
    roots: Set[str] = set()
    # Common locations
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    for base in ["/media", "/mnt", "/run/media"]:
        roots.add(base)
        if user:
            roots.add(os.path.join(base, user))
    # Jetson typical
    roots.add("/media/jetson")
    # Parse /proc/mounts for removable-ish filesystems
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
    # Only keep ones that exist
    return [r for r in sorted(roots) if os.path.exists(r)]

DEFAULT_MOUNT_ROOTS = guess_mount_roots()

@dataclass
class ShipmentList:
    barcodes: List[str]

    @staticmethod
    def parse(text: str) -> Optional["ShipmentList"]:
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
        tried_paths = 0
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
                # Case-insensitive match for candidate filenames
                lower_files = {fn.lower(): fn for fn in filenames}
                for cand_lower in self.filename_candidates:
                    if cand_lower in lower_files:
                        found_name = lower_files[cand_lower]
                        full = os.path.join(dirpath, found_name)
                        tried_paths += 1
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
        if tried_paths == 0:
            self.status.emit("Scanning for USB + barcodes file... (no candidates seen yet)")


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

        # Debug log is visible now
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


class ShipScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Ship")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 36))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)


class ViewOrderScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("View Order")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 36))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)


class MainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pallet Portal GUI (Robust USB-gated + Menu)")
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
