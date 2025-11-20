import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
from pyzbar import pyzbar
import numpy as np
import cv2

# Initialize GStreamer
Gst.init(None)

# GStreamer camera pipeline
pipeline_str = (
    "nvarguscamerasrc sensor-id=0 ! "
    "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! "
    "nvvidconv ! video/x-raw, format=BGRx ! "
    "videoconvert ! video/x-raw, format=BGR ! appsink name=sink emit-signals=False"
)

pipeline = Gst.parse_launch(pipeline_str)
appsink = pipeline.get_by_name("sink")
appsink.set_property("max-buffers", 1)
appsink.set_property("drop", True)
appsink.set_property("sync", False)

pipeline.set_state(Gst.State.PLAYING)
print("Press 'q' to quit...")

try:
    while True:
        # Pull sample from camera
        sample = appsink.emit("pull-sample")
        if sample is None:
            continue

        buf = sample.get_buffer()
        caps = sample.get_caps()
        width = caps.get_structure(0).get_value("width")
        height = caps.get_structure(0).get_value("height")

        ok, map_info = buf.map(Gst.MapFlags.READ)
        if not ok:
            continue

        frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
        buf.unmap(map_info)

        # Preprocess for barcode detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        gray_small = cv2.resize(gray, (640, int(640*gray.shape[0]/gray.shape[1])))

        # Decode barcodes
        barcodes = pyzbar.decode(gray_small)
        if barcodes:
            for barcode in barcodes:
                # Scale coordinates back to original frame
                x, y, w, h = barcode.rect
                scale_x = frame.shape[1] / gray_small.shape[1]
                scale_y = frame.shape[0] / gray_small.shape[0]
                x = int(x*scale_x)
                y = int(y*scale_y)
                w = int(w*scale_x)
                h = int(h*scale_y)

                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                text = f"{barcode_data} ({barcode_type})"

                # Draw rectangle and label
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 255, 0), 2)
                print("Detected:", text)

        # Display camera feed
        cv2.imshow("Jetson Barcode Feed", frame)

        # Quit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    pass
finally:
    pipeline.set_state(Gst.State.NULL)
    cv2.destroyAllWindows()
