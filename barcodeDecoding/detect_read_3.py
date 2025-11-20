import os
import sys
import argparse
import glob
import time

import cv2
import numpy as np
from ultralytics import YOLO
from pyzbar.pyzbar import decode as zbar_decode


parser = argparse.ArgumentParser(
    description="YOLO detect + robust barcode decoding (fast & readable)"
)
parser.add_argument('--model', required=True, help='Path to YOLO model file (e.g., "my_model.pt")')
parser.add_argument('--source', required=True, help='Image | folder | video | "usb0" | "picamera0"')
parser.add_argument('--thresh', type=float, default=0.5, help='YOLO detection confidence threshold (default 0.5)')
parser.add_argument('--resolution', default=None, help='WxH (e.g., "1280x720"). If omitted, use source resolution.')
parser.add_argument('--record', action='store_true', help='Record video/webcam to demo1.avi (requires --resolution).')


parser.add_argument('--decode_every', type=int, default=2,
                    help='Decode only every Nth frame (default 2). 1 = decode every frame.')
parser.add_argument('--fallback_fullframe', action='store_true',
                    help='If ROIs fail to decode, also try full-frame decoding.')
parser.add_argument('--target_fps', type=float, default=4.0,
                    help='Cap processing/display FPS (default 4).')
parser.add_argument('--wait_ms', type=int, default=100,
                    help='cv2.waitKey delay per frame in ms (default 100).')


parser.add_argument('--pad', type=int, default=8, help='Pixels to pad around each ROI (default 8).')
parser.add_argument('--pad_pct', type=float, default=0.06,
                    help='Extra padding as fraction of bbox size (default 0.06).')
parser.add_argument('--shrink', type=float, default=0.10,
                    help='Shrink bbox % on each side to cut background (default 0.10).')


parser.add_argument('--min_roi_width', type=int, default=360,
                    help='If ROI width < this, upscale before decoding (default 360 px).')
parser.add_argument('--upscale_factor', type=float, default=2.0,
                    help='Base upscale factor when ROI is small (default 2.0).')


parser.add_argument('--variants', type=int, default=3, choices=[1,2,3],
                    help='1=basic(gray+upscale), 2=+CLAHE, 3=+adaptive threshold (default 3).')


parser.add_argument('--print_debug', action='store_true', help='Also print bbox/conf info for debugging.')

args = parser.parse_args()


model_path = args.model
img_source = args.source
conf_thresh = float(args.thresh)
user_res = args.resolution
record = bool(args.record)

decode_every = max(1, int(args.decode_every))
fallback_fullframe = bool(args.fallback_fullframe)
target_fps = max(0.5, float(args.target_fps))
wait_ms = max(1, int(args.wait_ms))

pad_px = max(0, int(args.pad))
pad_pct = max(0.0, float(args.pad_pct))
shrink = min(max(0.0, float(args.shrink)), 0.45)  # clamp to avoid inverting boxes

min_roi_w = max(60, int(args.min_roi_width))
upscale_factor = max(1.0, float(args.upscale_factor))
variant_level = int(args.variants)

print_debug = bool(args.print_debug)

if not os.path.exists(model_path):
    print('ERROR: Model path is invalid or not found.')
    sys.exit(1)


model = YOLO(model_path, task='detect')
labels = model.names  

def label_name_for(cls_id):
    if isinstance(labels, dict):
        return str(labels.get(cls_id, cls_id))
    if isinstance(labels, (list, tuple)) and 0 <= cls_id < len(labels):
        return str(labels[cls_id])
    return str(cls_id)


img_ext_list = ['.jpg','.JPG','.jpeg','.JPEG','.png','.PNG','.bmp','.BMP']
vid_ext_list = ['.avi','.mov','.mp4','.mkv','.wmv']

if os.path.isdir(img_source):
    source_type = 'folder'
elif os.path.isfile(img_source):
    _, ext = os.path.splitext(img_source)
    if ext in img_ext_list:
        source_type = 'image'
    elif ext in vid_ext_list:
        source_type = 'video'
    else:
        print(f'Unsupported file extension: {ext}')
        sys.exit(1)
elif img_source.startswith('usb'):
    source_type = 'usb'
    try:
        usb_idx = int(img_source[3:])  
    except ValueError:
        print('For USB, use "usb0", "usb1", etc.')
        sys.exit(1)
elif img_source.startswith('picamera'):
    source_type = 'picamera'
    try:
        picam_idx = int(img_source[8:])  
    except ValueError:
        picam_idx = 0
else:
    print(f'Invalid --source: {img_source}')
    sys.exit(1)


resize = False
if user_res:
    resize = True
    try:
        resW, resH = map(int, user_res.lower().split('x'))
    except Exception:
        print('Bad --resolution format. Use WxH, e.g., 1280x720')
        sys.exit(1)

if record:
    if source_type not in ['video','usb','picamera']:
        print('Recording only works for video/camera sources.')
        sys.exit(1)
    if not user_res:
        print('Please specify --resolution to record.')
        sys.exit(1)
    record_name = 'demo1.avi'
    record_fps = min(30, max(1, int(target_fps)))
    recorder = cv2.VideoWriter(
        record_name,
        cv2.VideoWriter_fourcc(*'MJPG'),
        record_fps,
        (resW, resH)
    )


if source_type == 'image':
    imgs_list = [img_source]
elif source_type == 'folder':
    imgs_list = [f for f in glob.glob(os.path.join(img_source, '*'))
                 if os.path.splitext(f)[1] in img_ext_list]
    imgs_list.sort()
    if not imgs_list:
        print('No images found in folder.')
        sys.exit(1)
elif source_type in ['video','usb']:
    cap_arg = img_source if source_type == 'video' else usb_idx
    cap = cv2.VideoCapture(cap_arg)
    if not cap.isOpened():
        print('Failed to open video/camera source.')
        sys.exit(1)
    if user_res:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resW)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resH)

    cap.set(cv2.CAP_PROP_FPS, target_fps)
elif source_type == 'picamera':
    try:
        from picamera2 import Picamera2
    except Exception:
        print('Picamera2 not available. Install picamera2 or use another source.')
        sys.exit(1)
    cap = Picamera2()
    if not user_res:
        resW, resH = 1280, 720
        resize = True
    cap.configure(cap.create_video_configuration(
        main={"format": 'XRGB8888', "size": (resW, resH)}))
    cap.start()


bbox_colors = [(164,120,87), (68,148,228), (93,97,209), (178,182,133), (88,159,106),
               (96,202,231), (159,124,168), (169,162,241), (98,118,150), (172,176,184)]
avg_frame_rate = 0.0
frame_rate_buffer, fps_avg_len = [], 200
img_count = 0
frame_index = 0
frame_period = 1.0 / target_fps  # seconds

def tighten_and_pad(x1, y1, x2, y2, w, h, shrink_frac, pad_px, pad_pct):
    
    bw, bh = x2 - x1, y2 - y1
    sx = int(bw * shrink_frac)
    sy = int(bh * shrink_frac)
    x1 += sx; x2 -= sx
    y1 += sy; y2 -= sy

   
    bw, bh = x2 - x1, y2 - y1
    ex = int(bw * pad_pct) + pad_px
    ey = int(bh * pad_pct) + pad_px
    x1 = max(0, x1 - ex)
    y1 = max(0, y1 - ey)
    x2 = min(w, x2 + ex)
    y2 = min(h, y2 + ey)

    
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)

def ensure_min_width(roi_bgr, min_w, up_factor):
    if roi_bgr is None:
        return None
    h, w = roi_bgr.shape[:2]
    if w >= min_w:
        return roi_bgr
    scale = max(up_factor, float(min_w) / max(1, w))
    return cv2.resize(roi_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)

def try_decode_variants(gray, level):
    """
    level 1: gray + upscale only
    level 2: + CLAHE
    level 3: + adaptive threshold
    Tries rotations at each step. Returns list of decoded strings or [].
    """
    variants = []

   
    variants.append(gray)

    # upscale
    up = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)
    variants.append(up)

    if level >= 2:
        
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        up_eq = clahe.apply(up)
        variants.append(up_eq)

    if level >= 3:
        
        thr = cv2.adaptiveThreshold(up, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 7)
        variants.append(thr)

    
    for img in variants:
        for rot in (None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE):
            test = img if rot is None else cv2.rotate(img, rot)
            dec = zbar_decode(test)
            if dec:
                out = []
                for d in dec:
                    if d.data:
                        try:
                            out.append(d.data.decode('utf-8', errors='ignore'))
                        except Exception:
                            pass
                if out:
                    return out
    return []

def decode_roi(roi_bgr, min_w, up_factor, level):
    if roi_bgr is None:
        return []
    roi_bgr = ensure_min_width(roi_bgr, min_w, up_factor)
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    # gentle denoise can help
    gray = cv2.bilateralFilter(gray, 7, 75, 75)
    # mild sharpen
    kernel = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])
    gray = cv2.filter2D(gray, -1, kernel)
    return try_decode_variants(gray, level)

def decode_fullframe(frame, level):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 75, 75)
    return try_decode_variants(gray, level)

# Main Loop
while True:
    loop_start = time.perf_counter()
    frame_index += 1

    # Acquire frame
    if source_type in ['image','folder']:
        if img_count >= len(imgs_list):
            print('All images processed. Exiting.')
            break
        frame = cv2.imread(imgs_list[img_count])
        if frame is None:
            print(f'Failed to read image: {imgs_list[img_count]}')
            break
        img_count += 1
    elif source_type == 'video':
        ret, frame = cap.read()
        if not ret or frame is None:
            print('Reached end of video. Exiting.')
            break
    elif source_type == 'usb':
        ret, frame = cap.read()
        if not ret or frame is None:
            print('Camera read failed. Exiting.')
            break
    elif source_type == 'picamera':
        frame_bgra = cap.capture_array()
        if frame_bgra is None:
            print('Picamera read failed. Exiting.')
            break
        frame = cv2.cvtColor(np.copy(frame_bgra), cv2.COLOR_BGRA2BGR)

    if resize:
        frame = cv2.resize(frame, (resW, resH))

    h, w = frame.shape[:2]

    # YOLO inference
    results = model(frame, conf=conf_thresh, verbose=False)
    boxes = results[0].boxes

    decoded_strings = []  
    object_count = 0

    # Decode only every Nth frame to keep things smooth
    do_decode = (frame_index % decode_every == 0)

    # Go through detections
    num_boxes = 0 if boxes is None else len(boxes)
    for i in range(num_boxes):
        xyxy = boxes[i].xyxy
        if xyxy is None:
            continue
        xyxy = xyxy.cpu().numpy().squeeze().astype(int)
        x1, y1, x2, y2 = map(int, xyxy.tolist())

        cls_id = int(boxes[i].cls.item()) if boxes[i].cls is not None else -1
        cls_name = label_name_for(cls_id)
        conf = float(boxes[i].conf.item()) if boxes[i].conf is not None else 0.0

        
        tp = tighten_and_pad(x1, y1, x2, y2, w, h, shrink, pad_px, pad_pct)
        if tp:
            px1, py1, px2, py2 = tp
        else:
            px1, py1, px2, py2 = x1, y1, x2, y2

        roi = frame[py1:py2, px1:px2]

        
        color = bbox_colors[cls_id % 10] if cls_id >= 0 else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        lbl = f'{cls_name}:{int(conf*100)}%'
        ty = max(y1, 20)
        cv2.putText(frame, lbl, (x1, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 2)
        cv2.putText(frame, lbl, (x1, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)

        # Decode ROI (only on scheduled frames)
        texts = []
        if do_decode:
            roi_up = ensure_min_width(roi, min_roi_w, upscale_factor)
            texts = decode_roi(roi_up, min_roi_w, upscale_factor, variant_level)

        
        y_offset = ty + 18
        for t in texts:
            decoded_strings.append(t)
            show = (t[:38] + '…') if len(t) > 39 else t
            cv2.putText(frame, f'CODE: {show}', (x1, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,0,0), 2)
            cv2.putText(frame, f'CODE: {show}', (x1, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 1)
            y_offset += 18

        object_count += 1

    
    if do_decode and not decoded_strings and fallback_fullframe:
        ff_texts = decode_fullframe(frame, variant_level)
        decoded_strings.extend(ff_texts)

    
    if do_decode:
        if decoded_strings:
            print(f"\nFrame {frame_index} decoded:")
           
            seen = set()
            for t in decoded_strings:
                if t not in seen:
                    print("  " + t)
                    seen.add(t)
        else:
            print(f"\nFrame {frame_index}: no codes decoded")

        if print_debug and boxes is not None:
            print(f"  (debug) detections: {len(boxes)}")
            for i in range(len(boxes)):
                xyxy = boxes[i].xyxy.cpu().numpy().squeeze().astype(int)
                dx1, dy1, dx2, dy2 = map(int, xyxy.tolist())
                cls_id = int(boxes[i].cls.item()) if boxes[i].cls is not None else -1
                cls_name = label_name_for(cls_id)
                conf = float(boxes[i].conf.item()) if boxes[i].conf is not None else 0.0
                print(f"   - {cls_name} conf={conf:.3f} bbox=({dx1},{dy1},{dx2},{dy2})")

    
    cv2.putText(frame, f'Decoded: {len(decoded_strings)}  Detections: {object_count}',
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

    cv2.imshow('YOLO + Robust Barcode Reader', frame)
    if record:
        recorder.write(frame)

    
    loop_end_after_draw = time.perf_counter()
    inst_fps = 1.0 / max(1e-6, (loop_end_after_draw - loop_start))
    if len(frame_rate_buffer) >= fps_avg_len:
        frame_rate_buffer.pop(0)
    frame_rate_buffer.append(inst_fps)
    avg_frame_rate = float(np.mean(frame_rate_buffer))

    
    key = cv2.waitKey(wait_ms if source_type in ['video','usb','picamera'] else 1)
    if key in (ord('q'), ord('Q')):
        break
    elif key in (ord('p'), ord('P')):
        try:
            cv2.imwrite('capture.png', frame)
            print("Saved capture.png")
        except Exception:
            pass

    
    if source_type in ['video','usb','picamera']:
        elapsed = time.perf_counter() - loop_start
        sleep_needed = frame_period - elapsed
        if sleep_needed > 0:
            time.sleep(sleep_needed)


if source_type in ['video','usb']:
    cap.release()
elif source_type == 'picamera':
    cap.stop()
if record:
    recorder.release()
cv2.destroyAllWindows()
print(f'Average pipeline FPS: {avg_frame_rate:.2f}')
