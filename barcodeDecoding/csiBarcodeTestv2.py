# Single-CSI barcode detection on Jetson (no WSL), similar structure to face_detect

import cv2
import numpy as np
from pyzbar.pyzbar import decode  # pip install pyzbar ; sudo apt install libzbar0

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1280, capture_height=720,
    display_width=1280, display_height=720,
    framerate=30, flip_method=0
):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id}{mode} ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, "
        f"framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, width=(int){display_width}, height=(int){display_height}, format=(string)BGRx ! "
        "videoconvert ! video/x-raw, format=(string)BGR ! appsink drop=True"
    )

def enhance(img):
    # Optional: helps pyzbar on low-contrast, stretch-wrapped pallets
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8)).apply(gray)
    blur  = cv2.GaussianBlur(clahe, (0,0), 1.0)
    sharp = cv2.addWeighted(clahe, 1.5, blur, -0.5, 0)
    return sharp

def main():
    pipeline = gstreamer_pipeline(sensor_id=0, flip_method=0)
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("Unable to open CSI camera. Check ribbon seating and nvargus-daemon.")
        return

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # Optional pre-processing (comment out if unnecessary)
            proc = enhance(frame)
            # pyzbar accepts grayscale or BGR; we’ll pass grayscale
            if len(proc.shape) == 3:
                proc = cv2.cvtColor(proc, cv2.COLOR_GRAY2BGR)  # keep drawing in color window
                gray = cv2.cvtColor(proc, cv2.COLOR_BGR2GRAY)
            else:
                gray = proc

            for code in decode(gray):
                data = code.data.decode('utf-8', errors='ignore')
                # Draw polygon around the barcode
                pts = np.array(code.polygon, dtype=np.int32).reshape((-1,1,2))
                cv2.polylines(proc, [pts], True, (0,255,0), 2)
                x,y,w,h = code.rect
                cv2.putText(proc, data, (x, y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

                # Print once per detection (you can de-bounce as needed)
                print(data)

            cv2.imshow("Barcode CSI Camera", proc)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q')):  # ESC or q
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
