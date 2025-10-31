'''
this version is built on v15 to implement the Pillow barcode detection and pyzbar decoding from Simeon's code(s)
'''

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

#---GPIO for the Jetson Orin Nano---
try:
    import Jetson.GPIO as GPIO #from nvidia jetson gpio docs
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

BARCODE_FILENAME_CANDIDATES = ["barcodes.txt"] #this looks for the manifest text file on the flashdrive
REQUIRED_COUNT = 10 #this was just for testing count detection
REQUIRED_LENGTH = 10 #helps avoid auto reads that arent real barcodes

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

DEFAULT_MOUNT_ROOTS = guess_mount_roots() #this gets the possible usb mount points

@dataclass
class ShipmentList:
    def __init__(self, barcodes):
        self.barcodes = barcodes

    @staticmethod
    def parse(text: str):
        if text and text[0] == "\ufeff":
            text = text[1:]

        tokens = re.findall(r"(?<!\d)\d{10}(?!\d)", text) #based on stackoverflow regex for grabbing 10-digit barcodes

        seen = set()
        unique_tokens = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                unique_tokens.append(t)

        return ShipmentList(unique_tokens) if len(unique_tokens) == 10 else None


class USBWatcher(QObject):
    validListFound = pyqtSignal(ShipmentList, str)
    status = pyqtSignal(str)

    def __init__(self, mount_roots=None, filename_candidates=None, poll_ms=1000, parent=None):
        super().__init__(parent)
        self.mount_roots = mount_roots or DEFAULT_MOUNT_ROOTS
        self.filename_candidates = [c.lower() for c in (filename_candidates or BARCODE_FILENAME_CANDIDATES)] #this looks for the manifest text file on the flashdrive
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
                            self.status.emit(f"{found_name} at {dirpath} did not contain exactly {REQUIRED_COUNT} unique {REQUIRED_LENGTH}-digit barcodes.") #this was just for testing count detection
        self.status.emit("Scanning for USB + barcodes file...")

# --------------------Welcome & Menu Screens--------------------
class WelcomeScreen(QWidget):
    proceed = pyqtSignal(ShipmentList, str)

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

        self.watcher = USBWatcher() #creates the usb monitor for barcodes
        self.watcher.status.connect(self._on_status)
        self.watcher.validListFound.connect(self._on_valid)
        self.watcher.start() #starts watching for usb insert

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R: #press r to manually rescan usb
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


class MenuScreen(QWidget): #handles the menu input and navigation
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

# --------------------ship screen with ping sensor wait--------------------
PING_PINS_BOARD = [15, 32]
DETECTION_THRESHOLD_IN = 18
MB1040_US_PER_INCH = 147.0


class PingWorker(QThread): #thread that reads ping sensors without crosstalk
    """
    Crosstalk-safe ultrasonic polling thread.
    - Alternates sensors with long settle time between switching (like jetson_ping_crosstalk).
    - Adds a short quiet period after each read.
    - Averages multiple pulse-width samples, trimming outliers.
    - Emits ready(distance_inches, pin_used) ONLY when distance <= DETECTION_THRESHOLD_IN.
    - Never returns after first reading; loops until stopped.
    """
    ready = pyqtSignal(float, int)
    log = pyqtSignal(str)

    def __init__(self, pins_board: List[int]):
        super().__init__()
        self.pins = [p for p in pins_board if p is not None]
        self._stop = False

        self.settle_time_s = 3.0
        self.quiet_time_s = 0.5
        self.samples = 7

    def stop(self):
        self._stop = True

    def run(self):
        if not GPIO_AVAILABLE:
            self.log.emit("GPIO not available; simulating sensor after 1s.")
            time.sleep(1.0)
            self._emit_log_and_maybe_ready(24.0, -1)
            return

        try:
            GPIO.setmode(GPIO.BOARD) #standard jetson gpio pin mode setup
            for p in self.pins:
                GPIO.setup(p, GPIO.IN)

            self.log.emit(f"Starting ping initialization with crosstalk-safe alternation on pins (BOARD): {self.pins}")
            last_pin = None
            while not self._stop:
                for pin in self.pins:
                    if self._stop:
                        break

                    if last_pin is None or pin != last_pin:
                        self.log.emit(f"Reading sensor on pin {pin} (settle {self.settle_time_s:.1f}s)...")
                        self._sleep(self.settle_time_s)
                    else:
                        self.log.emit(f"Reading sensor on pin {pin}...")

                    dist_in = self._read_distance_in(pin, samples=self.samples)

                    if dist_in is not None:
                        self.log.emit(f"Pin {pin}: {dist_in:.2f} in")
                        self._emit_log_and_maybe_ready(dist_in, pin)
                    else:
                        self.log.emit(f"Pin {pin}: no valid reading (timeout / noise).")

                    last_pin = pin
                    self._sleep(self.quiet_time_s)

        except Exception as e:
            self.log.emit(f"PingWorker error: {e!r}")
        finally:
            self._cleanup()

    def _emit_log_and_maybe_ready(self, dist_in: float, pin: int):
        try:
            threshold = DETECTION_THRESHOLD_IN
        except NameError:
            threshold = 18
        if dist_in <= threshold:
            self.ready.emit(dist_in, pin) #sends signal when distance is under threshold

    def _sleep(self, seconds: float):
        end = time.time() + seconds
        while not self._stop and time.time() < end:
            time.sleep(0.01) #tiny delay to smooth readings

    def _cleanup(self):
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup() #cleanup per jetson gpio best practice
            except Exception:
                pass

    # --- Low-level pulse width sampling ---
    def _measure_pw_us(self, pin: int, timeout_s: float = 0.06) -> Optional[float]:
        """
        Measure the pulse width (in microseconds) of one MB1040 echo.
        Returns None on timeout.
        """
        start = time.time()
        while GPIO.input(pin) == GPIO.HIGH:
            if self._stop or (time.time() - start) > timeout_s:
                return None
        while GPIO.input(pin) == GPIO.LOW:
            if self._stop or (time.time() - start) > timeout_s:
                return None
        rise = time.perf_counter()
        while GPIO.input(pin) == GPIO.HIGH:
            if self._stop or (time.time() - start) > timeout_s:
                return None
        fall = time.perf_counter()
        return (fall - rise) * 1e6 #convert echo pulse to microseconds

    def _read_distance_in(self, pin: int, samples: int = 7) -> Optional[float]:
        pws = []
        for _ in range(samples):
            if self._stop:
                return None
            pw = self._measure_pw_us(pin)
            if pw is None:
                continue
            dist_in = pw / MB1040_US_PER_INCH
            if 1.0 <= dist_in <= 300.0:
                pws.append(dist_in)
            time.sleep(0.01) #tiny delay to smooth readings

        if not pws:
            return None

        pws.sort()
        if len(pws) >= 5:
            pws = pws[1:-1]
        return sum(pws) / len(pws)


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
        self.log.setVisible(True) #keep visible per user
        layout.addWidget(self.log)

        self._expected_codes = [] #this will hold the manifest barcodes from usb
        self._barcode_worker = None #this gets created after ping ready

        pins = list(PING_PINS_BOARD)
        if OPTIONAL_SECOND_PIN is not None:
            pins.append(OPTIONAL_SECOND_PIN)
        self.worker = PingWorker(pins)
        self.worker.log.connect(self._log)
        self.worker.ready.connect(self._on_ready)
        self.worker.start()

    def set_manifest_codes(self, codes):
        #this gets called by mainwindow after usb watcher succeeds
        self._expected_codes = list(codes or [])

    def _log(self, msg: str):
        self.log.append(msg)

    def _on_ready(self, dist_in: float, pin: int):
        self.status.setText("CSI cameras are starting...") #starts camera after ping ready
        self._log(f"ready from pin {pin}, distance ~{dist_in:.2f} in")
        if self._barcode_worker is None:
            self._barcode_worker = BarcodeReaderWorker(
                model_path="my_model.pt",
                sensor_id=0,
                width=1280, height=720, framerate=30,
                min_conf=0.25, iou=0.45, max_rois=6,
                decode_every=1, fallback_interval=15,
                manifest_codes=self._expected_codes
            )
            self._barcode_worker.log.connect(self._log)
            self._barcode_worker.finished_all.connect(self._on_all_done)
            self._barcode_worker.start()

    def _on_all_done(self):
        self.status.setText("all barcodes found — scanning complete")
        try:
            if self.worker.isRunning():
                self.worker.stop()
        except Exception:
            pass

    def closeEvent(self, e):
        try:
            if self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(500)
        except Exception:
            pass
        try:
            if self._barcode_worker and self._barcode_worker.isRunning():
                self._barcode_worker.stop()
                self._barcode_worker.wait(800)
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

# --------------------Main window--------------------

# --------------------embedded: simple manifest matcher--------------------
#this wraps the usb-loaded barcodes into a simple matcher for exact checks
#based on manifest_matcher.py ideas (load and case-insensitive lookup)
class SimpleManifestMatcher:
    #this keeps a set and a dict for quick exact matches
    def __init__(self, codes):
        self.codes = [str(c).strip() for c in (codes or []) if str(c).strip()]
        self._lut = {c.lower(): c for c in self.codes}  #lower for lookup, keep original for echo #based on manifest_matcher.py lookup map
    def match(self, code: str):
        if not code:
            return None, 0, "none"
        key = str(code).strip().lower()
        if key in self._lut:
            return self._lut[key], 100, "exact"  #exact match like teammate script prints #based on manifest_matcher.py match()
        return None, 0, "none"

# --------------------embedded: CSI camera barcode reader worker--------------------
#this uses pillow + yolo + pyzbar + gstreamer to read barcodes from the csi cam
#based on yolo_pillow_manifest.py functions and loop
from PyQt5.QtCore import pyqtSignal, QThread

class BarcodeReaderWorker(QThread):
    log = pyqtSignal(str)          #this shows in the ship screen debug box
    decoded = pyqtSignal(str)      #this fires for every decoded barcode
    matched = pyqtSignal(str, int, str)  #value, score, method
    finished_all = pyqtSignal()    #this fires when all manifest barcodes are found

    def __init__(self, model_path="my_model.pt", sensor_id=0, width=1280, height=720, framerate=30,
                 min_conf=0.25, iou=0.45, max_rois=6, decode_every=1, fallback_interval=15,
                 manifest_codes=None):
        super().__init__()
        self.model_path = model_path
        self.sensor_id = sensor_id
        self.width = width
        self.height = height
        self.framerate = framerate
        self.min_conf = min_conf
        self.iou = iou
        self.max_rois = max_rois
        self.decode_every = decode_every
        self.fallback_interval = fallback_interval
        self._stop = False
        self._manifest_codes = list(manifest_codes or [])
        self._found = set()  #this tracks matched codes until we hit all #based on user's request to stop when all found

    def stop(self):
        self._stop = True

    # --- pipeline helpers (based on yolo_pillow_manifest.py lines ~30-60) ---
    def _make_pipeline(self):
        #this builds the gstreamer string for nvargus
        #based on yolo_pillow_manifest.py make_pipeline()
        return (
            f"nvarguscamerasrc sensor-id={self.sensor_id} ! "
            f"video/x-raw(memory:NVMM), width={self.width}, height={self.height}, framerate={self.framerate}/1 ! "
            f"nvvidconv ! video/x-raw, format=BGRx ! "
            f"videoconvert ! video/x-raw, format=BGR ! "
            f"appsink name=sink emit-signals=false max-buffers=1 drop=true sync=false"
        )

    def _pull_frame(self, appsink):
        #based on yolo_pillow_manifest.py pull_frame()
        sample = appsink.emit("pull-sample")
        if sample is None:
            return None
        buf = sample.get_buffer()
        caps = sample.get_caps()
        width = caps.get_structure(0).get_value("width")
        height = caps.get_structure(0).get_value("height")
        ok, map_info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return None
        try:
            import numpy as np
            frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
            return frame
        finally:
            buf.unmap(map_info)

    def _yolo_rois(self, model, img):
        #based on yolo_pillow_manifest.py yolo_rois()
        res = model.predict(img, conf=self.min_conf, iou=self.iou, verbose=False)
        if not res or len(res) == 0 or res[0].boxes is None or res[0].boxes.xyxy is None:
            return []
        boxes = res[0].boxes
        import numpy as np
        xyxy = boxes.xyxy.cpu().numpy().astype(int)
        if xyxy.size == 0:
            return []
        confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.ones((xyxy.shape[0],), dtype=float)
        areas = (xyxy[:,2]-xyxy[:,0]) * (xyxy[:,3]-xyxy[1])
        areas = (xyxy[:,2]-xyxy[:,0]) * (xyxy[:,3]-xyxy[:,1])
        order = np.argsort(-(confs * (areas.clip(min=1))))
        xyxy = xyxy[order][:self.max_rois]
        out = [(int(x1), int(y1), int(x2), int(y2)) for x1, y1, x2, y2 in xyxy]
        return out

    def _decode_from_rois(self, img_rgb, rois):
        #based on yolo_pillow_manifest.py decode_from_rois()
        from PIL import ImageOps
        from pyzbar.pyzbar import decode as zbar_decode
        out = []
        for (x1, y1, x2, y2) in rois:
            x1 = max(0, x1); y1 = max(0, y1); x2 = min(img_rgb.width, x2); y2 = min(img_rgb.height, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            crop = img_rgb.crop((x1, y1, x2, y2))
            crop_gray = ImageOps.grayscale(crop)
            res = zbar_decode(crop_gray)
            for r in res:
                try:
                    val = r.data.decode('utf-8', errors='ignore')
                except Exception:
                    val = None
                if val and val not in out:
                    out.append(val)
        return out

    def run(self):
        try:
            from ultralytics import YOLO  #based on yolo_pillow_manifest.py import
            from PIL import Image         #we convert frames to pillow
            import gi                     #gstreamer introspection
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst
            globals()['Gst'] = Gst
        except Exception as e:
            self.log.emit(f"[error] imports failed: {e} #based on yolo_pillow_manifest.py imports")
            return

        try:
            matcher = SimpleManifestMatcher(self._manifest_codes)
            Gst.init(None)
            pipeline_str = self._make_pipeline()
            pipeline = Gst.parse_launch(pipeline_str)
            appsink = pipeline.get_by_name("sink")
            if appsink is None:
                self.log.emit("[error] appsink 'sink' not found #based on yolo_pillow_manifest.py")
                return
            pipeline.set_state(Gst.State.PLAYING)
            self.log.emit("[info] csi pipeline started #based on yolo_pillow_manifest.py")

            self.log.emit(f"[info] loading yolo: {self.model_path}")
            model = YOLO(self.model_path)

            frame_idx = 0
            expected_total = len(self._manifest_codes)
            if expected_total == 0:
                self.log.emit("[warn] no manifest barcodes loaded")
            else:
                self.log.emit(f"[info] expecting {expected_total} barcodes from manifest")

            while not self._stop:
                frame_bgr = self._pull_frame(appsink)
                if frame_bgr is None:
                    continue
                frame_idx += 1
                if self.decode_every > 1 and (frame_idx % self.decode_every != 0):
                    continue

                img_rgb = Image.fromarray(frame_bgr[:, :, ::-1], mode="RGB")  #this converts bgr to rgb for pillow #based on yolo_pillow_manifest.py
                rois = self._yolo_rois(model, img_rgb)
                decoded = self._decode_from_rois(img_rgb, rois)

                if not decoded and self.fallback_interval > 0 and (frame_idx % self.fallback_interval == 0):
                    from PIL import ImageOps
                    from pyzbar.pyzbar import decode as zbar_decode
                    ff_gray = ImageOps.grayscale(img_rgb)
                    for r in zbar_decode(ff_gray):
                        try:
                            val = r.data.decode('utf-8', errors='ignore')
                        except Exception:
                            val = None
                        if val and val not in decoded:
                            decoded.append(val)

                if decoded:
                    ts = time.strftime("%H:%M:%S")
                    for val in decoded:
                        self.decoded.emit(val)
                        rec, score, method = matcher.match(val)
                        if rec:
                            self.matched.emit(rec, score, method)
                            self._found.add(rec.strip())
                            self.log.emit(f"[{ts}] barcode: {val} -> match [{method}:{score}] in manifest")
                        else:
                            self.log.emit(f"[{ts}] barcode: {val} -> not in manifest")
                    if expected_total and len(self._found) >= expected_total:
                        self.log.emit("[info] all barcodes found — scanning complete")
                        self.finished_all.emit()
                        break

            try:
                pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass

        except Exception as e:
            self.log.emit(f"[error] barcode reader crashed: {e}")
            try:
                pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
        finally:
            pass

class MainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pallet Portal GUI (USB-gated + Menu + Ping)")
        self.setMinimumSize(900, 600)

        self.welcome = WelcomeScreen()
        self.menu = MenuScreen()
        self.ship = ShipScreen()
        self.view = ViewOrderScreen()

        self.addWidget(self.welcome)
        self.addWidget(self.menu)
        self.addWidget(self.ship)
        self.addWidget(self.view)

        self.setCurrentIndex(0)
        self.welcome.proceed.connect(self._unlock_to_menu)
        self.menu.shipSelected.connect(lambda: self.setCurrentIndex(2)) #goes to ship screen
        self.menu.viewOrderSelected.connect(lambda: self.setCurrentIndex(3)) #goes to view order screen

    def _unlock_to_menu(self, shipment, source):
        self.expected_barcodes = shipment.barcodes
        self.ship_source = source
        try:
            self.ship.set_manifest_codes(self.expected_barcodes)  #this hands the manifest to ship screen
        except Exception:
            pass
        self.setCurrentIndex(1)
        self.menu.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv) #starts the qt app
    w = MainWindow() #creates the main window
    w.show() #shows the window
    sys.exit(app.exec_()) #keeps the app running until closed