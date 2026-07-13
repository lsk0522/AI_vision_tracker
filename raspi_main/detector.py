import cv2
import time
import threading
import numpy as np
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

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
        if YOLO is not None:
            self.model = YOLO('best_int8.tflite', task='detect')
        else:
            self.model = None
        self.active = False
        
    def start_tracking(self):
        self.active = True
        
    def stop_tracking(self):
        self.active = False
        
    def track(self, frame):
        if not self.active or self.model is None:
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
    while True:
        try:
            # ── 추적 ────────────────────────────────────────
            ball = None

            if state.control_mode == 'auto':
                # 라즈베리파이 자체 YOLO는 CPU를 마비시켜 조이스틱 전환 렉을 유발하므로 비활성화하고,
                # 오직 노트북 원격 추적 결과(state.ball)만 사용하여 동작하도록 최적화합니다.
                # 주의: 여기에 `import time`을 다시 넣으면 안 됨 — 함수 안에서 import하면
                # time이 함수 전체의 지역변수로 잡혀, 위쪽 time.time() 호출들이 전부
                # UnboundLocalError로 죽어 detector 스레드가 시작 즉시 조용히 사망한다.
                _yolo.stop_tracking()
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

            # 참고: state.point(모터 조준점) 갱신은 routes/detector_routes.py 의
            # set_target(스무딩·클램프) + 타겟 소실 워치독이 단독으로 담당한다.
            # 이 루프에서 point 를 함께 쓰면 두 스레드가 서로 다른 값으로 경쟁하며
            # 모터가 떨리므로 여기서는 state.ball(UI 표시용) 관리만 한다.

        except Exception as e:
            print(f"[Detector] Exception in _run loop: {e}")
        
        # 10ms 대기를 주어 CPU 점유율을 제어하고 GIL 양보
        time.sleep(0.01)
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
