import time
from ultralytics import YOLO
import cv2
import numpy as np

model = YOLO('best_int8.tflite', task='detect')
frame = np.zeros((480, 640, 3), dtype=np.uint8)

print("Testing default imgsz...")
t0 = time.time()
try:
    model(frame, verbose=False, conf=0.25)
    print(f"Default imgsz took: {time.time() - t0:.3f}s")
except Exception as e:
    print(f"Failed: {e}")

print("Testing imgsz=160...")
t0 = time.time()
try:
    model(frame, imgsz=160, verbose=False, conf=0.25)
    print(f"imgsz=160 took: {time.time() - t0:.3f}s")
except Exception as e:
    print(f"Failed: {e}")
