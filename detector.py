import cv2
import time
import threading
import numpy as np
from ultralytics import YOLO

import state

# ── 칼만 필터 ────────────────────────────────────────────
class KalmanTracker:
    def __init__(self):
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        self.kf.transitionMatrix = np.array([
            [1, 0, 1, 0], [0, 1, 0, 1],
            [0, 0, 1, 0], [0, 0, 0, 1]], np.float32)
        self.kf.processNoiseCov     = np.eye(4, dtype=np.float32) * 5.0
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 1.0
        self.kf.errorCovPost        = np.eye(4, dtype=np.float32) * 10.0
        self.initialized = False
        self.lost = 0
        self.MAX_LOST = 20

    def update(self, cx, cy):
        m = np.array([[np.float32(cx)], [np.float32(cy)]])
        if not self.initialized:
            self.kf.statePost = np.array(
                [[np.float32(cx)], [np.float32(cy)], [0.0], [0.0]], np.float32)
            self.initialized = True
        self.kf.correct(m)
        self.lost = 0
        p = self.kf.predict()
        return int(p[0][0]), int(p[1][0])

    def predict_next(self):
        if not self.initialized:
            return None
        self.lost += 1
        if self.lost > self.MAX_LOST:
            self.initialized = False
            return None
        p = self.kf.predict()
        return int(p[0][0]), int(p[1][0])

    def reset(self):
        self.initialized = False
        self.lost = 0


# ── YOLO 트래커 (단독 AI) ──────────────────────────────────
class YOLOTracker:
    def __init__(self):
        self.model = YOLO('best_int8.tflite', task='detect')
        self.active = False
        
    def start_tracking(self):
        self.active = True
        
    def stop_tracking(self):
        self.active = False
        
    def track(self, frame):
        if not self.active:
            return None
            
        results = self.model(frame, verbose=False, conf=0.25)
        
        if len(results) > 0 and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            best_box = None
            max_conf = -1
            
            for box in boxes:
                conf = float(box.conf[0])
                if conf > max_conf:
                    max_conf = conf
                    best_box = box
                    
            if best_box is not None:
                x1, y1, x2, y2 = map(int, best_box.xyxy[0])
                w = x2 - x1
                h = y2 - y1
                cx = x1 + w // 2
                cy = y1 + h // 2
                
                return {
                    "cx": cx, "cy": cy,
                    "x": x1, "y": y1, "w": w, "h": h,
                    "conf": max_conf,
                    "predicted": False,
                    "detector": "yolo"
                }
        return None

# ── 모듈 인스턴스 ────────────────────────────────────────
_yolo = YOLOTracker()
_kalman = KalmanTracker()
_thread = None

def get_learning_progress():
    return 100

def reset_tracker():
    _kalman.reset()
    state.ball = None
    state.ball_lost = False
    state.learning_progress = 0

# ── 메인 루프 ────────────────────────────────────────────
def _run():
    last_id = None

    while True:
        try:
            frame = state.current_frame
            if frame is None:
                time.sleep(0.01)
                continue

            frame_id = id(frame)
            if frame_id == last_id:
                time.sleep(0.005)
                continue
            last_id = frame_id

            # ── 추적 ────────────────────────────────────────
            ball = None

            if state.control_mode == 'auto':
                _yolo.start_tracking()
                ball = _yolo.track(frame)
            else:
                _yolo.stop_tracking()
                ball = None

            # ── 칼만 갱신 ────────────────────────────────────
            if ball:
                px, py = _kalman.update(ball["cx"], ball["cy"])
                ball["predicted_cx"] = px
                ball["predicted_cy"] = py
                state.ball      = ball
                state.ball_lost = False
            elif state.control_mode == 'auto':
                pred = _kalman.predict_next()
                state.ball_lost = True
                state.ball = (
                    {"cx": pred[0], "cy": pred[1], "predicted": True, "detector": "kalman"}
                    if pred else None
                )
            else:
                state.ball      = None
                state.ball_lost = False
                
        except Exception as e:
            print(f"[Detector] Exception in _run loop: {e}")
            time.sleep(0.1)

        # ── 자동 모드: 조준점 고정 (조이스틱/모터 보호) ──
        if state.control_mode == "auto":
            # 무조건 화면 정중앙 좌표로 고정시켜 모터가 임의로 움직이지 않도록 함
            state.point[0] = 320
            state.point[1] = 240

def start():
    global _thread
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()

def set_learn_zone(x, y, w, h):
    pass

def get_learn_zone():
    return (170, 90, 300, 300)

def start_learning(n_samples=20):
    pass
