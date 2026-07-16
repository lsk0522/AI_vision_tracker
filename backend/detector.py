import cv2
import time
import threading
import numpy as np
from mediapipe_detector import MediaPipeDetector

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
# YOLOTracker removed. Using MediaPipeDetector.

# ── 모듈 인스턴스 ────────────────────────────────────────
_mp_tracker = MediaPipeDetector(mode="hand")
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
                # 원격 추적을 우선시하고, 원격 추적이 끊기면 로컬 MediaPipe 사용
                if getattr(state, 'remote_tracking_last_time', 0.0) > 0 and (time.time() - state.remote_tracking_last_time < 2.0):
                    ball = state.ball
                else:
                    if state.current_frame is not None:
                        ball = _mp_tracker.detect(state.current_frame)
                    else:
                        ball = None
            else:
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
