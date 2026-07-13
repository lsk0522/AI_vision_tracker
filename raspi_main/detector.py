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
                # 라즈베리파이 자체 YOLO는 CPU를 마비시켜 조이스틱 전환 렉을 유발하므로 비활성화하고,
                # 오직 노트북 원격 추적 결과(state.ball)만 사용하여 동작하도록 최적화합니다.
                _yolo.stop_tracking()
                import time
                if getattr(state, 'remote_tracking_last_time', 0.0) > 0 and (time.time() - state.remote_tracking_last_time < 2.0):
                    ball = state.ball
                else:
                    ball = None
            else:
                _yolo.stop_tracking()
                ball = None
                state.ball = None

            # ── 갱신 ────────────────────────────────────
            if ball:
                state.ball      = ball
                state.ball_lost = False
            else:
                state.ball      = None
                state.ball_lost = False
                
        except Exception as e:
            print(f"[Detector] Exception in _run loop: {e}")
            time.sleep(0.1)

        if state.control_mode == "auto":
            center_x, center_y = 320, 240
            if frame is not None:
                frame_h, frame_w = frame.shape[:2]
                center_x, center_y = frame_w // 2, frame_h // 2

            if state.ball:
                tx = state.ball["cx"]
                ty = state.ball["cy"]

                # 1차 저주파 필터 (Alpha = 0.35) 적용하여 뚝뚝 끊기는 좌표를 부드럽게 보간
                alpha = 0.35
                if not hasattr(state, '_smooth_tx'):
                    state._smooth_tx = float(tx)
                    state._smooth_ty = float(ty)
                else:
                    state._smooth_tx = state._smooth_tx + alpha * (float(tx) - state._smooth_tx)
                    state._smooth_ty = state._smooth_ty + alpha * (float(ty) - state._smooth_ty)

                tx_smooth = state._smooth_tx
                ty_smooth = state._smooth_ty

                err_x = tx_smooth - center_x
                err_y = ty_smooth - center_y

                # 한 번에 꺾이는 최대 범위를 160픽셀로 확장 (더 빠르고 정확하게)
                err_x = max(-160, min(160, err_x))
                err_y = max(-160, min(160, err_y))

                state.point[0] = int(center_x + err_x)
                state.point[1] = int(center_y + err_y)
            else:
                # 타겟을 놓치면 스무딩 상태 초기화 및 즉시 정지(중앙 좌표)
                if hasattr(state, '_smooth_tx'):
                    delattr(state, '_smooth_tx')
                if hasattr(state, '_smooth_ty'):
                    delattr(state, '_smooth_ty')
                state.point[0] = center_x
                state.point[1] = center_y
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
