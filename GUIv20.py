'''
this version builds on v17 and updates:
- usb manifest accepts any size/length (no fixed digit/length checks)
- dual ping worker triggers csi when either sensor <= 13 in (keeps 3s spacing)
- csi runs at 5fps and logs "no barcodes read" until a barcode shows up
- logs "<code> is loaded" or "<code> is not part of shipment" for each decode
'''

import os
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget, QTextEdit
)

#---gpio availability check (actual import happens inside worker)---
try:
    import Jetson.GPIO as _GPIO  #not used directly here, just a presence check
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

BARCODE_FILENAME_CANDIDATES = ["barcodes.txt"]  #only this filename per your request

def guess_mount_roots():
    #this grabs common usb mount points on ubuntu/jetson
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

DEFAULT_MOUNT_ROOTS = guess_mount_roots()  #this gets the possible usb mount points

# --------------------shipment list parsing--------------------
@dataclass
class ShipmentList:
    #this just carries the list of barcodes from the text file
    def __init__(self, barcodes):
        self.barcodes = barcodes

    @staticmethod
    def parse(text: str):
        #strip bom if present
        if text and text[0] == "\ufeff":
            text = text[1:]
        # accept any length and format: split on commas or whitespace
        # allows numeric or alphanumeric barcodes of any length
        parts = [t.strip() for t in re.split(r"[\s,]+", text) if t.strip()]
        # uniq while preserving order
        seen = set()
        uniq = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        return ShipmentList(uniq) if uniq else None

# --------------------usb watcher--------------------
class USBWatcher(QObject):
    validListFound = pyqtSignal(ShipmentList, str)
    status = pyqtSignal(str)

    def __init__(self, mount_roots=None, filename_candidates=None, poll_ms=1000, parent=None):
        super().__init__(parent)
        self.mount_roots = mount_roots or DEFAULT_MOUNT_ROOTS
        self.filename_candidates = [c.lower() for c in (filename_candidates or BARCODE_FILENAME_CANDIDATES)]  #looks for the manifest text file on the flashdrive
        self.timer = QTimer(self)
        self.timer.setInterval(poll_ms)
        self.timer.timeout.connect(self.scan_once)

    def start(self):
        self.scan_once()
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def scan_once(self):
        any_found = False
        for root in self.mount_roots:
            if not os.path.exists(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                #limit walk depth
                depth = dirpath.strip(os.sep).count(os.sep) - root.strip(os.sep).count(os.sep)
                if depth > 2:
                    dirnames[:] = []
                    continue
                if any(p in dirpath for p in ("/proc", "/sys", "/dev", "/run/lock")):
                    continue
                lower_files = {fn.lower(): fn for fn in filenames}
                for cand_lower in self.filename_candidates:
                    if cand_lower in lower_files:
                        any_found = True
                        found_name = lower_files[cand_lower]
                        full = os.path.join(dirpath, found_name)
                        try:
                            text = Path(full).read_text(encoding="utf-8", errors="ignore")
                        except Exception as e:
                            self.status.emit(f"found {found_name} at {dirpath}, but couldn't read it: {e}")
                            continue
                        parsed = ShipmentList.parse(text)
                        if parsed:
                            self.status.emit(f"valid list found at: {full}")
                            self.validListFound.emit(parsed, dirpath)
                            return
                        else:
                            self.status.emit(f"{found_name} at {dirpath} did not contain any readable barcodes")
        if not any_found:
            self.status.emit("scanning for usb + barcodes file...")

# --------------------welcome & menu screens--------------------
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

        self.watcher = USBWatcher()  #creates the usb monitor for barcodes
        self.watcher.status.connect(self._on_status)
        self.watcher.validListFound.connect(self._on_valid)
        self.watcher.start()  #starts watching for usb insert

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R:  #press r to manually rescan usb
            self._on_status("manual rescan requested.")
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

class MenuScreen(QWidget):  #handles the menu input and navigation
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

# -------------------- ws2812 strip + led worker --------------------
#this ws2812 control follows the idea in W2812.py for jetson nano
#based on: https://github.com/seitomatsubara/Jetson-nano-WS2812-LED-/blob/master/W2812.py
#note: this implementation uses rpi_ws281x on jetson. install it: pip3 install rpi-ws281x
from PyQt5.QtCore import QThread, pyqtSignal, QObject

#basic color helpers
def _clamp(v): return max(0, min(255, int(v)))
def rgb(r,g,b): return (_clamp(r), _clamp(g), _clamp(b))

#best-effort wrapper around rpi_ws281x; falls back to a no-op if lib is missing
class WS2812Strip:
    #this wraps pixelstrip so we can set pixels easily
    def __init__(self, count=5, gpio_bcm=18, brightness=128, freq_hz=800000, dma=10, invert=False, channel=0):
        self.count = count
        self.ok = False
        try:
            from rpi_ws281x import PixelStrip, Color  #based on W2812.py pattern
            self._Color = Color
            self.strip = PixelStrip(count, gpio_bcm, freq_hz, dma, invert, brightness, channel)
            self.strip.begin()
            self.ok = True
        except Exception as e:
            self.strip = None
            self._Color = None
            print(f"[warn] ws2812 init failed: {e}  #based on github W2812.py usage")

    def set_all(self, r, g, b, show=True):
        if not self.ok: return
        c = self._Color(_clamp(r), _clamp(g), _clamp(b))
        for i in range(self.count):
            self.strip.setPixelColor(i, c)
        if show: self.strip.show()

    def set_pixels(self, colors, show=True):
        if not self.ok: return
        for i, (r,g,b) in enumerate(colors[:self.count]):
            self.strip.setPixelColor(i, self._Color(_clamp(r), _clamp(g), _clamp(b)))
        if show: self.strip.show()

    def clear(self):
        self.set_all(0,0,0, show=True)

#led worker modes: standby rainbow, solid green, yellow pulse after first scan
class LEDWorker(QThread):
    #external controls
    to_standby = pyqtSignal()   #rainbow
    to_green = pyqtSignal()     #solid green
    to_yellow_pulse = pyqtSignal()  #two quick flashes then pause, loop

    def __init__(self, num_leds=5, gpio_bcm=18, brightness=128, parent=None):
        super().__init__(parent)
        self.strip = WS2812Strip(count=num_leds, gpio_bcm=gpio_bcm, brightness=brightness)
        self._mode = "standby"  #standby by default when gui is up
        self._stop = False

        #wire signals to local slots
        self.to_standby.connect(lambda: self._set_mode("standby"))
        self.to_green.connect(lambda: self._set_mode("green"))
        self.to_yellow_pulse.connect(lambda: self._set_mode("yellow_pulse"))

    def stop(self):
        self._stop = True

    def _set_mode(self, m):
        self._mode = m

    #rainbow helper like keyboard effect
    def _wheel(self, pos):
        #pos 0..255 -> r,g,b
        if pos < 85:
            return (pos*3, 255-pos*3, 0)
        if pos < 170:
            pos -= 85
            return (255-pos*3, 0, pos*3)
        pos -= 170
        return (0, pos*3, 255-pos*3)

    def run(self):
        #main loop ~50ms tick; patterns control their own timing
        idx = 0
        first_flash_done = False
        while not self._stop:
            try:
                if self._mode == "standby":
                    #rainbow wave across leds
                    if self.strip.ok:
                        colors = []
                        for i in range(self.strip.count):
                            colors.append(self._wheel((idx + i*10) % 256))
                        self.strip.set_pixels(colors)
                    self.msleep(50)  # ~20 fps standby
                elif self._mode == "green":
                    if self.strip.ok:
                        self.strip.set_all(0, 150, 0)  #solid green
                    self.msleep(150)  #slow tick
                elif self._mode == "yellow_pulse":
                    if self.strip.ok:
                        #two quick flashes then a pause (warehouse style)
                        #flash 1
                        self.strip.set_all(255, 160, 0)  #yellow
                        self.msleep(120)
                        self.strip.set_all(0, 0, 0)
                        self.msleep(120)
                        #flash 2
                        self.strip.set_all(255, 160, 0)
                        self.msleep(120)
                        self.strip.set_all(0, 0, 0)
                        #pause
                        self.msleep(600)
                    else:
                        self.msleep(200)
                else:
                    self.msleep(100)
                idx = (idx + 5) % 256
            except Exception:
                self.msleep(200)
        #cleanup
        try:
            if self.strip.ok:
                self.strip.clear()
        except Exception:
            pass

# ==================== dual ping worker (based on dual mb1040 script) ====================
#this handles both mb1040 sensors alternating safely with smoothing
#based on dual mb1040 script adapted from crosstalk_filteringv2
# ==================== dual ping worker (simplified instantaneous readings) ====================
class DualPingWorker(QThread):
    ready = pyqtSignal(float, str)  # (avg_distance_in, "either")
    log = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            import Jetson.GPIO as GPIO
        except Exception as e:
            self.log.emit(f"ping error: Jetson.GPIO not available: {e}")
            return

        import time

        # --- Pin assignments (BOARD numbering) ---
        SENSOR1_PIN = 15
        SENSOR2_PIN = 32

        # --- Sensor limits ---
        HARD_MIN_IN = 6.0
        MAX_IN = 254.0
        TRIGGER_IN = 13.0  # start CSI when either ≤ 13 in

        def measure_pulse(pin, timeout=0.05):
            """Measure one PWM pulse width (µs) with timeout."""
            if GPIO.wait_for_edge(pin, GPIO.RISING, timeout=int(timeout * 1000)) is None:
                return None
            start_ns = time.monotonic_ns()
            if GPIO.wait_for_edge(pin, GPIO.FALLING, timeout=int(timeout * 1000)) is None:
                return None
            end_ns = time.monotonic_ns()
            return (end_ns - start_ns) / 1000.0

        def read_distance(pin, label):
            """Read one instantaneous pulse and return distance in inches."""
            width_us = measure_pulse(pin)
            if width_us is None:
                self.log.emit(f"{label} → no pulse detected")
                return None
            distance_in = width_us / 147.0
            if not (HARD_MIN_IN <= distance_in <= MAX_IN):
                self.log.emit(f"{label} → out of range ({distance_in:.2f} in)")
                return None
            distance_cm = distance_in * 2.54
            self.log.emit(f"{label} → {distance_in:.2f} in ({distance_cm:.2f} cm)")
            return distance_in

        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(SENSOR1_PIN, GPIO.IN)
            GPIO.setup(SENSOR2_PIN, GPIO.IN)

            self.log.emit("alternating MB1040 readings every 3 s (instantaneous mode)...")
            while not self._stop:
                d1 = read_distance(SENSOR1_PIN, "sensor 1")
                time.sleep(0.1)  # crosstalk protection
                d2 = read_distance(SENSOR2_PIN, "sensor 2")

                if d1 is not None and d2 is not None:
                    avg = (d1 + d2) / 2.0
                    diff = d1 - d2
                    self.log.emit(f"→ Fused Avg: {avg:.2f} in | Offset: {diff:.2f} in")
                    if (d1 <= TRIGGER_IN) or (d2 <= TRIGGER_IN):
                        self.log.emit("one sensor < 13 in — ready to scan")
                        self.ready.emit(avg, "either")
                        break
                elif d1 is not None or d2 is not None:
                    active = d1 if d1 is not None else d2
                    self.log.emit(f"→ Single Sensor Active: {active:.2f} in")
                    if active <= TRIGGER_IN:
                        self.log.emit("single sensor < 13 in — ready to scan")
                        self.ready.emit(active, "either")
                        break
                else:
                    self.log.emit("→ both sensors out of range")

                time.sleep(3.0)

        except Exception as e:
            self.log.emit(f"ping error: {e}")
        finally:
            try:
                GPIO.cleanup()
            except Exception:
                pass
            self.log.emit("ping gpio cleaned up")


# ==================== embedded: simple manifest matcher ====================
#this wraps the usb-loaded barcodes into a simple matcher for exact checks
#based on manifest_matcher.py ideas (load and case-insensitive lookup)
class SimpleManifestMatcher:
    #this keeps a set and a dict for quick exact matches
    def __init__(self, codes):
        self.codes = [str(c).strip() for c in (codes or []) if str(c).strip()]
        # lower for lookup, keep original for echo
        self._lut = {c.lower(): c for c in self.codes}  #based on manifest_matcher.py lookup map

    def match(self, code: str):
        if not code:
            return None, 0, "none"
        key = str(code).strip().lower()
        if key in self._lut:
            # exact match like teammate script prints
            return self._lut[key], 100, "exact"  #based on manifest_matcher.py match()
        return None, 0, "none"

# ==================== embedded: csi camera barcode reader worker ====================
#this uses pillow + yolo + pyzbar + gstreamer to read barcodes from the csi cam
#based on yolo_pillow_manifest.py functions and loop
class BarcodeReaderWorker(QThread):
    log = pyqtSignal(str)          #this shows in the ship screen debug box
    decoded = pyqtSignal(str)      #this fires for every decoded barcode
    matched = pyqtSignal(str, int, str)  #value, score, method
    finished_all = pyqtSignal()    #this fires when all manifest barcodes are found

    def __init__(self, model_path="my_model.pt", sensor_id=0, width=1280, height=720, framerate=5,
                 min_conf=0.25, iou=0.45, max_rois=6, decode_every=1, fallback_interval=15,
                 manifest_codes=None):
        super().__init__()
        self.model_path = model_path
        self.sensor_id = sensor_id
        self.width = width
        self.height = height
        self.framerate = framerate  #now 5 fps
        self.min_conf = min_conf
        self.iou = iou
        self.max_rois = max_rois
        self.decode_every = decode_every
        self.fallback_interval = fallback_interval
        self._stop = False
        self._manifest_codes = list(manifest_codes or [])
        # this tracks matched codes until we hit all (per your request to stop when all found)
        self._found = set()

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
        #lazy imports so the rest of the gui can still load on dev machines
        #this mirrors teammate script pattern
        try:
            from ultralytics import YOLO  #based on yolo_pillow_manifest.py import
            from PIL import Image         #we convert frames to pillow
            import gi                     #gstreamer introspection
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst
            globals()['Gst'] = Gst  #stash for helpers
        except Exception as e:
            self.log.emit(f"[error] imports failed: {e} #based on yolo_pillow_manifest.py imports")
            return

        pipeline = None
        try:
            matcher = SimpleManifestMatcher(self._manifest_codes)  #this uses our usb-loaded list instead of auto
            #start camera pipeline (based on yolo_pillow_manifest.py main() gst section)
            Gst.init(None)
            pipeline_str = self._make_pipeline()
            pipeline = Gst.parse_launch(pipeline_str)
            appsink = pipeline.get_by_name("sink")
            if appsink is None:
                self.log.emit("[error] appsink 'sink' not found #based on yolo_pillow_manifest.py")
                return
            pipeline.set_state(Gst.State.PLAYING)
            self.log.emit("[info] csi pipeline started #based on yolo_pillow_manifest.py")

            #load model (based on yolo_pillow_manifest.py model load)
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
                    # still keep loop moving at ~5 fps
                    time.sleep(0.2)
                    self.log.emit("no barcodes read")
                    continue

                frame_idx += 1
                if self.decode_every > 1 and (frame_idx % self.decode_every != 0):
                    time.sleep(0.2)
                    self.log.emit("no barcodes read")
                    continue

                #convert bgr to pillow rgb (based on yolo_pillow_manifest.py Image.fromarray usage)
                img_rgb = Image.fromarray(frame_bgr[:, :, ::-1], mode="RGB")  #this converts bgr to rgb for pillow

                rois = self._yolo_rois(model, img_rgb)
                decoded = self._decode_from_rois(img_rgb, rois)

                #full frame fallback occasionally (based on yolo_pillow_manifest.py fallback_interval)
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
                    #report detections in requested phrasing
                    for val in decoded:
                        self.decoded.emit(val)
                        rec, score, method = matcher.match(val)
                        if rec:
                            self.matched.emit(rec, score, method)
                            self._found.add(rec.strip())
                            self.log.emit(f"{val} is loaded") #barcode decoded and IS on shipping manifest
                        else:
                            self.log.emit(f"{val} is not part of shipment") #barcode decoded but IS NOT on shipping manifest

                    #check completion
                    if expected_total and len(self._found) >= expected_total:
                        self.log.emit("all barcodes found — scanning complete")
                        self.finished_all.emit()
                        break
                else:
                    #no decodes this pass → say it
                    self.log.emit("no barcodes read") #keeps an active feed for testing and visualization purposes

                #enforce ~5 fps pacing
                time.sleep(0.2)

        except Exception as e:
            self.log.emit(f"[error] barcode reader crashed: {e}")

        finally:
            #stop pipeline when done
            try:
                if pipeline is not None:
                    pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass

# --------------------ship screen--------------------
class ShipScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Ship")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 36))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)

        #get led worker from the main window
        self._leds = None  #assigned in on_attach()

        self.status = QLabel("Waiting for ping sensor...")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setVisible(True)  #keep visible
        layout.addWidget(self.log)

        self._expected_codes = []     #this will hold the manifest barcodes from usb
        self._barcode_worker = None   #this gets created after ping ready

        #start the streamlined dual ping worker (either sensor under 13 in)
        self.worker = DualPingWorker()
        self.worker.log.connect(self._log)
        self.worker.ready.connect(self._on_ready)
        self.worker.start()

    def set_manifest_codes(self, codes):
        #this gets called by mainwindow after usb watcher succeeds
        self._expected_codes = list(codes or [])

    def _log(self, msg: str):
        self.log.append(msg)

    def _on_ready(self, dist_in: float, label: str):
        self.status.setText("CSI cameras are starting up...")  #requested wording

        if self._leds:
            self._leds.to_green.emit()  #turn on solid green when csi starts
            #flash yellow on first decode then keep pulsing
            def _first_decode(_val):
                if self._leds:
                    self._leds.to_yellow_pulse.emit()
                #disconnect this one-shot
                try:
                    self._barcode_worker.decoded.disconnect(_first_decode)
                except Exception:
                    pass
            self._barcode_worker.decoded.connect(_first_decode)


        self._log(f"sensor ready (~{dist_in:.2f} in avg) -> starting csi")
        #start barcode worker once
        if self._barcode_worker is None:
            self._barcode_worker = BarcodeReaderWorker(
                model_path="my_model.pt",   #this is the provided model filename
                sensor_id=0,                #use cam0 default like teammate script #based on yolo_pillow_manifest.py args
                width=1280, height=720, framerate=5,  #now 5 fps
                min_conf=0.25, iou=0.45, max_rois=6,  #same defaults
                decode_every=1, fallback_interval=15,
                manifest_codes=self._expected_codes
            )
            self._barcode_worker.log.connect(self._log)
            self._barcode_worker.finished_all.connect(self._on_all_done)
            self._barcode_worker.start()

    def _on_all_done(self):
        self.status.setText("all barcodes found — scanning complete")
        #stop ping worker too since we are done
        try:
            if hasattr(self, 'worker') and self.worker.isRunning():
                self.worker.stop()
        except Exception:
            pass

    def on_attach(self, main_window):
        #this is called by main to wire shared services like leds
        self._leds = getattr(main_window, "leds", None)

    def closeEvent(self, e):
        #stop threads on exit to prevent orphan processes
        try:
            if hasattr(self, 'worker') and self.worker.isRunning():
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

# --------------------view order screen--------------------
class ViewOrderScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("View Order")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Beausite Classic", 36))
        title.setStyleSheet("color: #0c2340; background-color: #f15a22; font-weight: bold;")
        layout.addWidget(title)

# --------------------main window--------------------
class MainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pallet Portal GUI (USB-gated + Menu + Dual Ping + CSI)")
        self.setMinimumSize(900, 600)

        self.welcome = WelcomeScreen()
        self.menu = MenuScreen()
      
        self.ship = ShipScreen()
        self.ship.on_attach(self)

        self.view = ViewOrderScreen()

        #when navigating to welcome or menu, keep rainbow active
        #welcome shown initially -> already standby
        self.menu.viewOrderSelected.connect(lambda: self.leds.to_standby.emit())
        self.menu.shipSelected.connect(lambda: None)  #ship will set its own mode

        self.addWidget(self.welcome)
        self.addWidget(self.menu)
        self.addWidget(self.ship)
        self.addWidget(self.view)

        self.setCurrentIndex(0)
        self.welcome.proceed.connect(self._unlock_to_menu)
        self.menu.shipSelected.connect(lambda: self.setCurrentIndex(2))  #goes to ship screen
        self.menu.viewOrderSelected.connect(lambda: self.setCurrentIndex(3))  #goes to view order screen

        #leds: one worker shared by all screens
        self.leds = LEDWorker(num_leds=5, gpio_bcm=18, brightness=128)  #gpio_bcm=18 uses pwm; adjust if needed
        self.leds.start()
        self.leds.to_standby.emit()  #rainbow on startup

    def _unlock_to_menu(self, shipment, source):
        self.expected_barcodes = shipment.barcodes
        self.ship_source = source
        try:
            self.ship.set_manifest_codes(self.expected_barcodes)  #hands the manifest to ship screen
        except Exception:
            pass
        self.setCurrentIndex(1)
        self.menu.setFocus()

    def closeEvent(self, e):
        try:
            if hasattr(self, "leds") and self.leds.isRunning():
                self.leds.stop()
                self.leds.wait(800)
        except Exception:
            pass
        super().closeEvent(e)

# --------------------entry point--------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)  #starts the qt app
    w = MainWindow()  #creates the main window
    w.show()  #shows the window
    sys.exit(app.exec_())  #keeps the app running until closed
