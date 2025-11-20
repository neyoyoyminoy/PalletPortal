import os
import sys
import argparse
import glob
import time

import cv2
import numpy as np
from ultralytics import YOLO


def gstreamer_pipeline(
    sensor_id=1,
    capture_width=1640,
    capture_height=1232,
    display_width=1280,
    display_height=720,
    framerate=30,
    flip_method=2,
):
    """Build a Jetson CSI camera pipeline string for OpenCV (GStreamer)."""
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, "
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! video/x-raw, format=(string)BGR ! appsink"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )


parser = argparse.ArgumentParser(
    description="YOLO detect: USB/video/images + Jetson CSI via GStreamer"
)
parser.add_argument(
    "--model",
    required=True,
    help='Path to YOLO model file (example: "runs/detect/train/weights/best.pt")',
)
parser.add_argument(
    "--source",
    required=True,
    help=(
        'Image file ("test.jpg"), folder ("imgs/"), video ("vid.mp4"), '
        'USB cam index ("usb0"), Jetson CSI ("csi0"), or Picamera2 ("picamera0").'
    ),
)
parser.add_argument(
    "--thresh",
    type=float,
    default=0.5,
    help='Minimum confidence threshold for drawing boxes (e.g. 0.4).',
)
parser.add_argument(
    "--resolution",
    default=None,
    help='WxH to display/infer at (e.g. "1280x720"). If omitted, uses source/native.',
)
parser.add_argument(
    "--record",
    action="store_true",
    help='Record video/webcam to "demo1.avi" (requires --resolution).',
)
# CSI-only quality controls (optional but handy)
parser.add_argument("--csi-fps", type=int, default=60, help="CSI framerate (default 60).")
parser.add_argument("--csi-flip", type=int, default=0, help="CSI flip-method (0..7; common: 0 or 2).")
parser.add_argument(
    "--csi-sensor",
    type=int,
    default=0,
    help="CSI sensor-id (0 for CAM0, 1 for CAM1 on many Jetson carriers).",
)

args = parser.parse_args()

model_path = args.model
img_source = args.source
min_thresh = float(args.thresh)
user_res = args.resolution
record = args.record

if not os.path.exists(model_path):
    print(
        "ERROR: Model path is invalid or model was not found. Make sure the model filename was entered correctly."
    )
    sys.exit(1)

model = YOLO(model_path, task="detect")
labels = model.names

img_ext_list = [
    ".jpg",
    ".JPG",
    ".jpeg",
    ".JPEG",
    ".png",
    ".PNG",
    ".bmp",
    ".BMP",
]
vid_ext_list = [".avi", ".mov", ".mp4", ".mkv", ".wmv"]

# Classify source type
if os.path.isdir(img_source):
    source_type = "folder"
elif os.path.isfile(img_source):
    _, ext = os.path.splitext(img_source)
    if ext in img_ext_list:
        source_type = "image"
    elif ext in vid_ext_list:
        source_type = "video"
    else:
        print(f"File extension {ext} is not supported.")
        sys.exit(1)
elif img_source.startswith("usb"):
    source_type = "usb"
    usb_idx = int(img_source[3:])
elif img_source.startswith("picamera"):
    source_type = "picamera"
    picam_idx = int(img_source[8:])
elif img_source.startswith("csi"):
    source_type = "csi"
    csi_idx = int(img_source[3:]) if len(img_source) > 3 else 0
else:
    print(f"Input {img_source} is invalid. Please try again.")
    sys.exit(1)

# Resolution handling
resize = False
if user_res:
    try:
        resW, resH = [int(x) for x in user_res.lower().split("x")]
        resize = True
    except Exception:
        print("--resolution must look like 1280x720")
        sys.exit(1)

# Optional recording
if record:
    if source_type not in ["video", "usb", "csi", "picamera"]:
        print("Recording only works for video and camera sources. Please try again.")
        sys.exit(1)
    if not user_res:
        print("Please specify --resolution to record video.")
        sys.exit(1)

    record_name = "demo1.avi"
    record_fps = 30
    recorder = cv2.VideoWriter(
        record_name, cv2.VideoWriter_fourcc(*"MJPG"), record_fps, (resW, resH)
    )

# Open capture per source
if source_type == "image":
    imgs_list = [img_source]
elif source_type == "folder":
    imgs_list = []
    for file in glob.glob(os.path.join(img_source, "*")):
        _, file_ext = os.path.splitext(file)
        if file_ext in img_ext_list:
            imgs_list.append(file)
elif source_type in ("video", "usb"):
    cap_arg = img_source if source_type == "video" else usb_idx
    cap = cv2.VideoCapture(cap_arg)
    if user_res:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resW)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resH)
elif source_type == "picamera":
    from picamera2 import Picamera2

    cap = Picamera2()
    if user_res:
        cap.configure(
            cap.create_video_configuration(main={"format": "XRGB8888", "size": (resW, resH)})
        )
    else:
        cap.configure(cap.create_video_configuration(main={"format": "XRGB8888"}))
    cap.start()
elif source_type == "csi":
    # Build GStreamer string for CSI and open with CAP_GSTREAMER
    if not user_res:
        # Use capture/display sizes the same if none is provided
        resW, resH = 1280, 720
    pipeline = gstreamer_pipeline(
        sensor_id=args.csi_sensor if img_source == "csi" else csi_idx,
        capture_width=resW,
        capture_height=resH,
        display_width=resW,
        display_height=resH,
        framerate=args.csi_fps,
        flip_method=args.csi_flip,
    )
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("Unable to open CSI camera via GStreamer. Check ribbon seating, camera enable, and nvargus-daemon.")
        sys.exit(1)

bbox_colors = [
    (164, 120, 87),
    (68, 148, 228),
    (93, 97, 209),
    (178, 182, 133),
    (88, 159, 106),
    (96, 202, 231),
    (159, 124, 168),
    (169, 162, 241),
    (98, 118, 150),
    (172, 176, 184),
]

avg_frame_rate = 0.0
frame_rate_buffer = []
fps_avg_len = 200
img_count = 0

window_title = "YOLO detection results"

while True:
    t_start = time.perf_counter()

    # ---- Grab a frame ----
    if source_type in ("image", "folder"):
        if img_count >= len(imgs_list):
            print("All images have been processed. Exiting program.")
            break
        img_filename = imgs_list[img_count]
        frame = cv2.imread(img_filename)
        img_count += 1
    elif source_type == "video":
        ret, frame = cap.read()
        if not ret:
            print("Reached end of the video file. Exiting program.")
            break
    elif source_type == "usb":
        ret, frame = cap.read()
        if not ret or frame is None:
            print(
                "Unable to read frames from the USB camera. Check connection. Exiting program."
            )
            break
    elif source_type == "picamera":
        frame_bgra = cap.capture_array()
        frame = cv2.cvtColor(np.copy(frame_bgra), cv2.COLOR_BGRA2BGR)
        if frame is None:
            print("Unable to read frames from the Picamera. Exiting program.")
            break
    elif source_type == "csi":
        ret, frame = cap.read()
        if not ret or frame is None:
            print(
                "Unable to read frames from the CSI camera (GStreamer). Check nvargus and camera."
            )
            break

    # Resize if requested (for display/inference)
    if resize:
        frame = cv2.resize(frame, (resW, resH))

    # ---- Inference ----
    results = model(frame, verbose=False)
    detections = results[0].boxes

    object_count = 0

    for i in range(len(detections)):
        xyxy = detections[i].xyxy.cpu().numpy().squeeze().astype(int)
        xmin, ymin, xmax, ymax = xyxy
        classidx = int(detections[i].cls.item())
        classname = labels[classidx]
        conf = float(detections[i].conf.item())

        if conf >= min_thresh:
            color = bbox_colors[classidx % len(bbox_colors)]
            cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)
            label = f"{classname}: {int(conf * 100)}%"
            labelSize, baseLine = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            label_ymin = max(ymin, labelSize[1] + 10)
            cv2.rectangle(
                frame,
                (xmin, label_ymin - labelSize[1] - 10),
                (xmin + labelSize[0], label_ymin + baseLine - 10),
                color,
                cv2.FILLED,
            )
            cv2.putText(
                frame,
                label,
                (xmin, label_ymin - 7),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
            )
            object_count += 1

    # HUD
    if source_type in ("video", "usb", "picamera", "csi"):
        cv2.putText(
            frame,
            f"FPS: {avg_frame_rate:0.2f}",
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
    cv2.putText(
        frame,
        f"Objects: {object_count}",
        (10, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
    )

    # Show & optionally record
    cv2.imshow(window_title, frame)
    if record:
        recorder.write(frame)

    # Keys
    key = cv2.waitKey(5 if source_type in ("video", "usb", "picamera", "csi") else 0)
    if key in (ord("q"), ord("Q")):
        break
    elif key in (ord("s"), ord("S")):
        cv2.waitKey()  # pause
    elif key in (ord("p"), ord("P")):
        cv2.imwrite("capture.png", frame)

    # FPS calc
    t_stop = time.perf_counter()
    frame_rate_calc = 1.0 / max(1e-6, (t_stop - t_start))
    if len(frame_rate_buffer) >= fps_avg_len:
        frame_rate_buffer.pop(0)
    frame_rate_buffer.append(frame_rate_calc)
    avg_frame_rate = float(np.mean(frame_rate_buffer))

# ---- Cleanup ----
print(f"Average pipeline FPS: {avg_frame_rate:.2f}")
if source_type in ("video", "usb", "csi"):
    cap.release()
elif source_type == "picamera":
    cap.stop()
if record:
    recorder.release()
cv2.destroyAllWindows()
