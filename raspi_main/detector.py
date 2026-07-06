import cv2
import os
import threading
import numpy as np
import time

import state

# 학습 영역: 640x480 프레임 중앙 300x300
_DEFAULT_LEARN_ZONE = (170, 90, 300, 300)   # (x, y, w, h)

# ── 헬퍼: 피부색 마스크 (YCrCb — 조명 변화에 강함) ──────
def _skin_mask(img):
    """피부색 픽셀 = 255, 그 외 = 0. 손을 제거하기 위해 사용."""
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    mask = cv2.inRange(ycrcb, np.array((0, 133, 77), dtype=np.uint8), np.array((255, 173, 127), dtype=np.uint8))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    return cv2.dilate(mask, kernel, iterations=2)   # 여유 있게 확장

# ── 헬퍼: 프레임 차분 모션 마스크 ────────────────────────
def _motion_mask(frame, prev_frame):
    diff = cv2.absdiff(
        cv2.cvtColor(frame,      cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY),
    )
    _, mask = cv2.threshold(diff, 15, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    return cv2.dilate(mask, kernel, iterations=2)

# ── 헬퍼: 밝은 환경 대비 개선 (CLAHE) ────────────────────
def _enhance_contrast(frame):
    """밝은 환경이나 역광에서 객체 인식률을 높이기 위해 대비를 극대화합니다."""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)

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

import threading

# ── CSRT 트래커 (최신 AI 트래커) ──────────────────────────
class CSRTTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.tracker = None
        self.active = False
        self.learning = False
        self.learn_zone: tuple[int,int,int,int] = (170, 90, 300, 300)  # (x,y,w,h)
        self.templates = [] # 다중 템플릿(360도 학습) 리스트 (최대 5장)
        self._start: float = 0.0
        self.load_saved_data()

    @property
    def progress(self):
        # 학습 모달을 즉시 완료시키기 위해 100 반환
        return 100

    def load_saved_data(self):
        import os
        folder = "learning_data"
        zone_path = os.path.join(folder, "learn_zone.txt")
        if os.path.exists(zone_path):
            try:
                with open(zone_path, "r") as f:
                    coords = [int(v) for v in f.read().strip().split(",")]
                    if len(coords) == 4:
                        self.learn_zone = (coords[0], coords[1], coords[2], coords[3])
            except Exception as e:
                pass

    def start_learning(self, n_samples=20):
        # 15초 학습 과정을 생략하고 즉시 트래커 초기화
        import state
        frame = state.current_frame
        if frame is None:
            state.learning_failed = True
            return

        x, y, w, h = self.learn_zone
        img_h, img_w = frame.shape[0], frame.shape[1]
        x1 = max(0, min(img_w - 1, x))
        y1 = max(0, min(img_h - 1, y))
        x2 = max(0, min(img_w, x + w))
        y2 = max(0, min(img_h, y + h))
        w = x2 - x1
        h = y2 - y1

        if w <= 0 or h <= 0:
            state.learning_failed = True
            return

        # 밝은 환경 대비 개선
        enhanced_frame = _enhance_contrast(frame)
        
        # ── GrabCut을 이용한 지능형 배경 제거 및 BBox 정밀 보정 ──
        # 사용자가 대충 친 박스(x1, y1, w, h) 주변의 배경(칠판, TV 등)을 AI로 싹둑 잘라내고,
        # 물체 본체에만 딱 맞는 정밀한 박스로 줄여서 CSRT 트래커가 배경에 속지 않게 만듭니다.
        try:
            # GrabCut은 연산이 무거우므로 ROI를 살짝 확장한 영역 안에서만 수행 (속도 최적화)
            pad = 20
            gx1 = max(0, x1 - pad)
            gy1 = max(0, y1 - pad)
            gx2 = min(img_w, x2 + pad)
            gy2 = min(img_h, y2 + pad)
            gw = gx2 - gx1
            gh = gy2 - gy1
            
            # 박스가 너무 작으면 GrabCut 생략
            if gw > 30 and gh > 30:
                grab_roi = enhanced_frame[gy1:gy2, gx1:gx2].copy()
                
                # GrabCut을 위한 초기 마스크 및 임시 배열 할당
                mask = np.zeros(grab_roi.shape[:2], np.uint8)
                bgdModel = np.zeros((1, 65), np.float64)
                fgdModel = np.zeros((1, 65), np.float64)
                
                # 사용자가 그린 박스 좌표를 ROI 내부 좌표계로 변환
                rx, ry, rw, rh = x1 - gx1, y1 - gy1, w, h
                
                # OpenCV GrabCut SegFault 방지: rect가 이미지 가장자리에 닿으면 세그멘테이션 오류 발생!
                if rx + rw >= gw: rw = gw - rx - 1
                if ry + rh >= gh: rh = gh - ry - 1
                if rw <= 0 or rh <= 0:
                    raise ValueError("Invalid GrabCut rect")
                
                rect = (rx, ry, rw, rh)
                
                # GrabCut 실행 (3번 반복) - rect 바깥은 확실한 배경, 안은 미정(아마 전경)
                cv2.grabCut(grab_roi, mask, rect, bgdModel, fgdModel, 3, cv2.GC_INIT_WITH_RECT)
                
                # 확실한 전경(1)이거나 아마 전경(3)인 부분만 1로, 나머진 0으로 마스킹
                fg_mask = np.where((mask == 1) | (mask == 3), 255, 0).astype('uint8')
                
                # 노이즈 제거를 위한 모폴로지 연산
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
                
                # 살아남은 전경 픽셀의 가장 큰 덩어리를 찾음
                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    largest = max(contours, key=cv2.contourArea)
                    rx, ry, rw, rh = cv2.boundingRect(largest)
                    
                    # 전경이 노이즈 수준이 아니라면 박스 갱신
                    if rw > 20 and rh > 20:
                        x1 = gx1 + rx
                        y1 = gy1 + ry
                        w = rw
                        h = rh
                        # 박스가 화면을 넘지 않도록 재검증
                        x1 = max(0, min(img_w - 1, x1))
                        y1 = max(0, min(img_h - 1, y1))
                        x2 = max(0, min(img_w, x1 + w))
                        y2 = max(0, min(img_h, y1 + h))
                        w = x2 - x1
                        h = y2 - y1
        except Exception as e:
            print(f"[GrabCut] Error during background removal: {e}")
            # 에러 발생 시 사용자가 그린 원본 박스를 그대로 사용

        try:
            # 다각도(Multi-Template) 학습: 새로운 각도의 이미지를 누적 저장
            new_template = enhanced_frame[y1:y1+h, x1:x1+w].copy()
            self.templates.append(new_template)
            if len(self.templates) > 5:
                self.templates.pop(0) # 최신 5개 각도만 유지
            
            new_tracker = getattr(cv2, 'TrackerCSRT_create')()  # type: ignore
            new_tracker.init(enhanced_frame, (x1, y1, w, h))
            
            # Thread-safe하게 갱신 (추적 스레드와 충돌 방지)
            with self.lock:
                self.tracker = new_tracker
                self.active = True
                self.learning = False
                state.learning_failed = False
                state.tracking_mode = "custom"
            
            # learn_zone을 갱신하지 않고 원본 박스를 유지하여,
            # "더 학습하기(반복학습)" 시 콕이 돌아가서 크기가 커져도 원본 박스 안에서 안전하게 잡히도록 합니다.
            self._save_thumbnail()
            
            # learn_zone 저장
            import os
            os.makedirs("learning_data", exist_ok=True)
            with open("learning_data/learn_zone.txt", "w") as f:
                f.write(f"{self.learn_zone[0]},{self.learn_zone[1]},{self.learn_zone[2]},{self.learn_zone[3]}")
                
        except Exception as e:
            print(f"[CSRTTracker] Error init: {e}")
            state.learning_failed = True
            self.active = False

    def process_frame(self, frame, prev_frame=None):
        pass

    def _finish(self):
        pass

    def _save_thumbnail(self):
        frame = state.current_frame
        if frame is None:
            return
        x, y, w, h = self.learn_zone
        img_h, img_w = frame.shape[0], frame.shape[1]
        x1 = max(0, min(img_w - 1, x))
        y1 = max(0, min(img_h - 1, y))
        x2 = max(0, min(img_w, x + w))
        y2 = max(0, min(img_h, y + h))
        if x2 > x1 and y2 > y1:
            roi = frame[y1:y2, x1:x2]
            import os
            os.makedirs("learning_data", exist_ok=True)
            try:
                cv2.imwrite("learning_data/target_thumbnail.jpg", roi, [cv2.IMWRITE_JPEG_QUALITY, 82])
            except Exception:
                pass

    def track(self, frame, motion=None):
        with self.lock:
            if not self.active or self.tracker is None:
                return None

            # 밝은 환경 대비 개선 적용
            enhanced_frame = _enhance_contrast(frame)

            ok, bbox = self.tracker.update(enhanced_frame)
            
            # ── 1. 정밀 트래킹 교정 (Local Template Drift Correction) ──
            # CSRT가 추적 중일 때, 사용자의 아이디어대로 "저장된 캡처 사진"과 현재 영역을 실시간으로 비교하여
            # 박스가 물체의 중심에서 살짝 벗어나는 현상(Drift)을 픽셀 단위로 완벽하게 교정합니다.
            if ok and len(self.templates) > 0:
                cx, cy, cw, ch = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                
                if cw > 10 and ch > 10:
                    pad = int(max(cw, ch) * 0.3) # 30% 주변 여유 공간 탐색
                    x1 = max(0, cx - pad)
                    y1 = max(0, cy - pad)
                    x2 = min(enhanced_frame.shape[1], cx + cw + pad)
                    y2 = min(enhanced_frame.shape[0], cy + ch + pad)
                    
                    roi = enhanced_frame[y1:y2, x1:x2]
                    
                    if roi.shape[0] >= ch and roi.shape[1] >= cw:
                        best_val = 0
                        best_loc = None
                        
                        # 현재 추정된 물체 크기(cw, ch)에 맞춰 저장된 사진들을 변환 후 정밀 비교
                        for tpl in self.templates:
                            stpl = cv2.resize(tpl, (cw, ch))
                            res = cv2.matchTemplate(roi, stpl, cv2.TM_CCOEFF_NORMED)
                            _, max_val, _, max_loc = cv2.minMaxLoc(res)
                            if max_val > best_val:
                                best_val = max_val
                                best_loc = max_loc
                                
                        # 일치율이 매우 높을 경우(0.75 이상)에만 CSRT의 오차를 교정 (비슷한 색상(배경/옷)에 끌려가지 않도록 방지)
                        if best_val > 0.75 and best_loc is not None:
                            corrected_x = x1 + best_loc[0]
                            corrected_y = y1 + best_loc[1]
                            bbox = (corrected_x, corrected_y, cw, ch)
                        # 만약 일치율이 극도로 낮다면(0.25 미만), 물체가 화면 밖으로 나갔거나 엉뚱한 배경을 잡은 것임!
                        elif best_val < 0.25:
                            ok = False
                            print(f"[CSRT] Target left screen or severe drift (score={best_val:.2f}). Forcing recovery.")
            
            # ── 2. 트래커 완전 실패 시 360도 다각도 템플릿 매칭 전역 복구 ──
            # 트래커가 대상을 완전히 놓쳤을 때(not ok), 저장된 최대 5개의 모든 각도 이미지를 꺼내어
            # 현재 화면에서 가장 비슷한 형태가 있는지 찾아냅니다. (배드민턴 콕 등 3D 회전 물체에 필수)
            if not ok and len(self.templates) > 0:
                best_val = 0
                best_loc = None
                best_tpl = None
                
                # 저장된 모든 각도의 템플릿과 비교 (크기 변화 대응을 위해 3가지 스케일 적용)
                for tpl in self.templates:
                    if tpl.shape[0] > 0 and tpl.shape[1] > 0:
                        for scale in (0.8, 1.0, 1.25):
                            stw = int(tpl.shape[1] * scale)
                            sth = int(tpl.shape[0] * scale)
                            # 스케일된 템플릿이 화면보다 크거나 너무 작으면 패스
                            if stw < 15 or sth < 15 or stw >= enhanced_frame.shape[1] or sth >= enhanced_frame.shape[0]:
                                continue
                            
                            stpl = cv2.resize(tpl, (stw, sth))
                            res = cv2.matchTemplate(enhanced_frame, stpl, cv2.TM_CCOEFF_NORMED)
                            _, max_val, _, max_loc = cv2.minMaxLoc(res)
                            
                            if max_val > best_val:
                                best_val = max_val
                                best_loc = max_loc
                                best_tpl = stpl
                
                if best_val > 0.48 and best_tpl is not None: # 잃어버렸지만 저장된 각도/크기 중 하나와 형태가 비슷하면
                    tw, th = best_tpl.shape[1], best_tpl.shape[0]
                    new_bbox = (best_loc[0], best_loc[1], tw, th)
                    self.tracker = getattr(cv2, 'TrackerCSRT_create')()  # type: ignore
                    self.tracker.init(enhanced_frame, new_bbox)
                    bbox = new_bbox
                    ok = True
                    print(f"[CSRT] Recovered via MULTI-TEMPLATE! score={best_val:.2f}, angles={len(self.templates)}")

            if not ok:
                return None

        x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        cx = x + w // 2
        cy = y + h // 2
        
        # 바운딩 박스 화면 이탈 방지
        frame_h, frame_w = frame.shape[:2]
        x = max(0, min(frame_w - 1, x))
        y = max(0, min(frame_h - 1, y))
        
        return {
            "cx": cx, "cy": cy,
            "x": x, "y": y, "w": w, "h": h,
            "matches": 100, "predicted": False
        }

    def reset(self):
        with self.lock:
            self.active = False
            self.learning = False
            self.tracker = None
            self.templates = []

# ── Hough Circle 폴백 (흰 공 등 원형 물체) ────────────────
class CircleDetector:
    """ORB 실패 시 폴백. 형태만 보므로 흰 공 ↔ 흰 배경도 감지 가능."""

    def detect(self, frame, motion=None):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 모션 영역만 사용 (배경 원형 노이즈 방지)
        search = gray
        if motion is not None and cv2.countNonZero(motion) > 200:
            search = cv2.bitwise_and(gray, gray, mask=motion)

        blurred = cv2.GaussianBlur(search, (9, 9), 2)

        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1, minDist=40,
            param1=60, param2=18,
            minRadius=12, maxRadius=130,
        )
        if circles is None:
            return None

        circles = np.round(circles[0]).astype(int)

        # 피부색 중심 원 제외 (손가락 끝 등)
        skin = _skin_mask(frame)
        best = None
        best_r = 0
        for cx, cy, r in circles:
            if 0 <= cy < frame.shape[0] and 0 <= cx < frame.shape[1]:
                if skin[cy, cx]:      # 중심이 피부색 → 손 가능성, 스킵
                    continue
                if r > best_r:
                    best_r = r
                    best = (cx, cy, r)

        if best is None:
            return None

        cx, cy, r = best
        return {
            "cx": int(cx), "cy": int(cy),
            "x": int(cx - r), "y": int(cy - r),
            "w": int(2 * r), "h": int(2 * r),
            "predicted": False,
            "detector": "hough",
        }

# ── 모듈 인스턴스 ────────────────────────────────────────
_csrt   = CSRTTracker()
_circle = CircleDetector()
_kalman = KalmanTracker()
_thread = None

def get_learning_progress():
    return _csrt.progress

def reset_tracker():
    _csrt.reset()
    _kalman.reset()
    state.ball = None
    state.ball_lost = False
    state.learning_progress = 0

# ── 메인 루프 ────────────────────────────────────────────
def _run():
    last_id    = None
    prev_frame = None

    while True:
        try:
            frame = state.current_frame
            if frame is None:
                time.sleep(0.01)
                continue

            # ── 학습 중 (CSRT에서는 즉시 완료됨) ─────────────────────────────────────
            if _csrt.learning:
                pass

            frame_id = id(frame)
            if frame_id == last_id:
                time.sleep(0.005)
                continue
            last_id = frame_id

            # ── 추적 ────────────────────────────────────────
            ball = None
            motion = None

            # 수동 모드일 때는 무거운 모션 마스크 및 트래킹을 생략 (단, 학습 중이 아닐 때)
            if state.control_mode == 'auto' or _csrt.learning:
                motion = _motion_mask(frame, prev_frame) if prev_frame is not None else None
                prev_frame = frame.copy()

                if state.target_type == "ball":
                    # 동그란 공 전용 트래킹 알고리즘: 원형 감지를 최우선으로 사용
                    ball_obj = _circle.detect(frame, motion)
                    if ball_obj:
                        ball = ball_obj
                        # 공이 감지되었지만 CSRT가 작동 중이면 (보조용으로) 업데이트만 수행
                        if _csrt.active:
                            _csrt.track(frame, motion)
                    else:
                        # 원형을 못 찾은 경우에만 CSRT 트래커를 보조로 사용
                        if _csrt.active:
                            ball = _csrt.track(frame, motion)
                else:
                    # 기타 사물 전용 (기존 방식): CSRT 템플릿 매칭을 1순위로 사용
                    if _csrt.active:
                        ball = _csrt.track(frame, motion)
                    
                    # CSRT 실패 시 보조 수단으로 원형 감지 시도 (원래 v1.0.0 로직)
                    if ball is None and motion is not None:
                        ball = _circle.detect(frame, motion)
            else:
                # 수동 모드 최적화: prev_frame만 최소한으로 유지
                if prev_frame is None:
                    prev_frame = frame.copy()

            # ── 칼만 갱신 ────────────────────────────────────
            if ball:
                px, py = _kalman.update(ball["cx"], ball["cy"])
                ball["predicted_cx"] = px
                ball["predicted_cy"] = py
                state.ball      = ball
                state.ball_lost = False
            elif _csrt.active:
                pred = _kalman.predict_next()
                state.ball_lost = True
                state.ball = (
                    {"cx": pred[0], "cy": pred[1], "predicted": True}
                    if pred else None
                )
            else:
                state.ball      = None
                state.ball_lost = False
                
        except Exception as e:
            print(f"[Detector] Exception in _run loop: {e}")
            time.sleep(0.1)

        # ── 자동 모드: 조준점 갱신 ───────────────────────
        if state.control_mode == "auto" and state.ball and frame is not None:
            tx = state.ball.get("predicted_cx", state.ball["cx"])
            ty = state.ball.get("predicted_cy", state.ball["cy"])
            
            # ESP32 펌웨어 내부에서 T명령을 받아 직접 제어하므로,
            # 파이썬 측 P-Controller는 제거하고 타겟의 순수 픽셀 좌표만 state.point에 넘깁니다.
            state.point[0] = int(tx)
            state.point[1] = int(ty)

def start():
    global _thread
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()

def set_learn_zone(x, y, w, h):
    _csrt.learn_zone = (int(x), int(y), int(w), int(h))

def get_learn_zone():
    return getattr(_csrt, 'learn_zone', _DEFAULT_LEARN_ZONE)

def start_learning(n_samples=20):
    _csrt.start_learning()
    _kalman.reset()
    state.ball = None
    state.ball_lost = False
    state.learning_progress = 0
