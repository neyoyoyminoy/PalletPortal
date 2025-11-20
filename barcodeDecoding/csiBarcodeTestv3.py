# YOLO only
# Jetson + OpenCV (GStreamer) + YOLO(ONNX) object detection for barcodes (no decoding)

import cv2
import numpy as np
import time

# ---------- Config ----------
ONNX_PATH = "barcode_yolo.onnx"   # <- put your YOLO ONNX path here
CONF_THRES = 0.35
NMS_THRES  = 0.45
INPUT_W, INPUT_H = 640, 640       # match your exported model size

# If your model has multiple classes, list them; else keep ["barcode"]
CLASS_NAMES = ["barcode"]
# Which class ids count as "barcode" (if model has more classes)
BARCODE_CLASS_IDS = {0}           # change if needed

# Use sensor-id=0 because gst-launch worked for you with 0
SENSOR_ID = 0

# Fallback: set to True to use a USB webcam (/dev/video0) instead of CSI
USE_USB = False
# ----------------------------

def gstreamer_pipeline(sensor_id=SENSOR_ID,
                       capture_w=1280, capture_h=720,
                       display_w=1280, display_h=720,
                       framerate=30, flip_method=0):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_w}, height=(int){capture_h}, "
        f"framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, width=(int){display_w}, height=(int){display_h}, format=(string)BGRx ! "
        "videoconvert ! video/x-raw, format=(string)BGR ! "
        "appsink drop=True max-buffers=1 sync=false"
    )

def letterbox(im, new_shape=(INPUT_H, INPUT_W)):
    h, w = im.shape[:2]
    r = min(new_shape[0] / h, new_shape[1] / w)
    new_unpad = (int(round(w * r)), int(round(h * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2; dh /= 2
    if (w, h) != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh-0.1)), int(round(dh+0.1))
    left, right = int(round(dw-0.1)), int(round(dw+0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114,114,114))
    return im, r, (dw, dh)

def load_net():
    net = cv2.dnn.readNetFromONNX(ONNX_PATH)
    try:
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA_FP16)
    except Exception:
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    return net

def infer(net, frame):
    ih, iw = frame.shape[:2]
    img, r, (dw, dh) = letterbox(frame, (INPUT_H, INPUT_W))
    blob = cv2.dnn.blobFromImage(img, 1/255.0, (INPUT_W, INPUT_H), swapRB=True, crop=False)
    net.setInput(blob)
    out = net.forward()  # YOLOv5/8 ONNX usually returns (1, N, 85) or (N, 85)

    # Normalize to (N, C)
    if out.ndim == 3:
        out = np.squeeze(out, axis=0)
    # Expect last dim: [cx, cy, w, h, conf, cls...] (YOLOv5/8 export)
    boxes  = []
    scores = []
    class_ids = []

    for det in out:
        if det.shape[-1] < 6:  # unexpected shape
            continue
        obj_conf = float(det[4])
        if obj_conf < CONF_THRES:
            continue
        cls_scores = det[5:]
        cls_id = int(np.argmax(cls_scores))
        conf = obj_conf * float(cls_scores[cls_id])
        if conf < CONF_THRES or cls_id not in BARCODE_CLASS_IDS:
            continue

        cx, cy, w, h = det[0], det[1], det[2], det[3]
        # Undo letterbox
        x = (cx - w/2 - dw) / (INPUT_W / iw / (1)) / (INPUT_W/iw)
        y = (cy - h/2 - dh) / (INPUT_H / ih / (1)) / (INPUT_H/ih)
        # The above is messy—do it cleanly using r, dw, dh:
        # From letterboxed coords -> original:
        bx = (cx - w/2 - dw) / r
        by = (cy - h/2 - dh) / r
        bw = w / r
        bh = h / r
        x1 = int(max(0, bx))
        y1 = int(max(0, by))
        x2 = int(min(iw - 1, bx + bw))
        y2 = int(min(ih - 1, by + bh))

        boxes.append([x1, y1, x2 - x1, y2 - y1])
        scores.append(float(conf))
        class_ids.append(cls_id)

    # NMS
    if boxes:
        idxs = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRES, NMS_THRES)
        idxs = idxs.flatten() if len(idxs) else []
    else:
        idxs = []

    return [boxes[i] for i in idxs], [scores[i] for i in idxs], [class_ids[i] for i in idxs]

def main():
    # Open camera
    if USE_USB:
        cap = cv2.VideoCapture(0)  # /dev/video0
    else:
        cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("Unable to open camera. If CSI, confirm GStreamer build and Argus; if USB, check /dev/video0.")
        return

    net = load_net()
    t0 = time.time(); frames = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        boxes, scores, cls_ids = infer(net, frame)

        for (x, y, w, h), s, cid in zip(boxes, scores, cls_ids):
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            label = f"{CLASS_NAMES[cid] if cid < len(CLASS_NAMES) else cid}: {s:.2f}"
            cv2.putText(frame, label, (x, max(0, y-7)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

        frames += 1
        if frames % 20 == 0:
            fps = frames / (time.time() - t0 + 1e-9)
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

        cv2.imshow("YOLO Barcode Detection (no decode)", frame)
        k = cv2.waitKey(1) & 0xFF
        if k in (27, ord('q')):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
