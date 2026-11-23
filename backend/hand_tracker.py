#!/usr/bin/env python3
"""
MediaPipe 손 추적 단독 실행기 — 기존 main.py(웹 대시보드)와 별개로 돌아갑니다.

  카메라 → MediaPipe Hands → "절대 각도" 목표 추정 → 필터/예측 → ESP32 (MOVE J XY)

기존 코드는 수정하지 않습니다.
  - 모터 연결/재연결/POS 피드백: motor_esp32.py, state.py 를 그대로 import 해서 사용
  - 펌웨어: 기존 v2.0.7 그대로 (MOVE J XY 절대 위치 명령 사용)

기존 T:x:y 방식과 다른 점
  - T:x:y 는 "ESP32가 명령을 받은 순간의 위치 + 오차" 로 목표를 잡습니다.
    카메라·검출 지연 동안 이미 움직인 만큼을 또 더하게 되어 지나쳤다 돌아오기 쉽고,
    그래서 기존 코드는 강한 스무딩(α=0.12)·클램프(±80px)로 눌러 놓은 상태입니다.
  - 여기서는 "프레임을 찍은 순간의 모터 위치 + 그 프레임에서의 오차" 로
    손의 절대 각도를 계산하고, 그 값을 알파-베타 필터로 다듬은 뒤
    지연만큼 앞을 예측한 절대 각도를 보냅니다. 같은 오차를 두 번 더하지 않습니다.
  - 목표는 새 검출이 있을 때만 1번 계산해서 보내고(예측은 최대 60px 분량),
    명령 1번 이동량을 제한하며, 손을 0.2초 놓치면 S 로 멈춥니다. (2026-11-20)
  - 시작할 때 CFG:MSL / CFG:ACC 를 보내고 응답으로 확인합니다 (--msl, --acc).
    카메라 노출·gain 은 기본으로 자동 밝기 조절(AutoBright, 0.5초마다 v4l2-ctl)을 하고,
    끝날 때 원래 값으로 되돌립니다. --exposure / --cam-gain 을 주면 그 값으로 고정
    (--exposure 0 = 카메라 자동 노출, --cam-gain -1 = gain 그대로 둠).
  - 기본값은 2026-11-20 실기 시험 결과 (acc 250, exposure 130, cam-gain 30,
    lead 0.18, max-lead-px 60). 자세한 내용은 docs/HANDOFF.md.

제스처 (기본): ✊ 주먹 = 따라가기, ✋ 손바닥(편 손) = 그 자리에서 정지.
  시작은 정지 상태이고, 손이 1초 넘게 안 보이면 다시 정지 상태로 돌아갑니다.
  항상 따라가게 하려면 --gesture any

실행 (라즈베리파이에서, main.py 는 꺼 둔 상태로):
  python hand_tracker.py                # 손 추적 시작
  python hand_tracker.py --calibrate    # 카메라-모터 게인 자동 측정 (처음 1회 권장)
  python hand_tracker.py --no-motor     # 모터 없이 검출/미리보기만
  미리보기: http://<파이주소>:5001/      (예: http://AIVisionTraker.local:5001/)
"""
import argparse
import json
import os
import socket
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

os.environ.setdefault("GLOG_minloglevel", "2")        # MediaPipe 내부 로그 줄이기
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

CALIB_PATH = os.path.join(HERE, "hand_tracker_calib.json")
REF_W, REF_H = 640, 480   # 펌웨어 픽셀 계약(중심 320:240) 기준 해상도


# ════════════════════════════════════════════════════════════════
# 카메라: 최신 프레임 1장만 유지 (버퍼 지연 최소화) + 촬영 시각 기록
# ════════════════════════════════════════════════════════════════
def _v4l2(dev, *args):
    import subprocess
    try:
        r = subprocess.run(["v4l2-ctl", "-d", dev, *args], capture_output=True, text=True, timeout=3)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def v4l2_apply(dev, ctrls):
    """v4l2-ctl 로 카메라 컨트롤 설정. ctrls: [(이름, 값)] 순서대로.
    반환: 원래 값 [(이름, 값)] (종료 때 되돌리기용). 없는 컨트롤은 건너뜀."""
    import shutil
    orig = []
    if not shutil.which("v4l2-ctl"):
        print("[camera] v4l2-ctl 이 없어 노출 설정을 건너뜁니다 (파이에서: sudo apt install v4l-utils)")
        return orig
    for name, val in ctrls:
        ok, out = _v4l2(dev, f"--get-ctrl={name}")
        if not ok or ":" not in out:
            continue                                  # 이 카메라에 없는 컨트롤
        orig.append((name, out.split(":")[-1].strip()))
        ok, out = _v4l2(dev, f"--set-ctrl={name}={val}")
        print(f"[camera] {name}={val}" + ("" if ok else f"  (실패: {out})"))
    return orig


class Camera:
    def __init__(self, index=None, width=640, height=480, fps=30, ctrls=None):
        self._backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
        idx = self._find() if index is None else index
        cap = cv2.VideoCapture(idx, self._backend)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            raise RuntimeError(f"카메라 {idx} 를 열 수 없습니다")
        self.cap = cap
        self.w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or width
        self.h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or height
        cc = int(cap.get(cv2.CAP_PROP_FOURCC))
        cc = "".join(chr((cc >> 8 * i) & 0xFF) for i in range(4)).strip("\0") or "?"
        print(f"[camera] index {idx}  {self.w}x{self.h}  {cc}  요청 {fps}fps → 드라이버 {cap.get(cv2.CAP_PROP_FPS):.0f}fps")
        self.dev = f"/dev/video{idx}"
        self._orig_ctrls = []
        if ctrls and sys.platform.startswith("linux"):
            self._orig_ctrls = v4l2_apply(self.dev, ctrls)
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._frame, self._t, self._seq = None, 0.0, 0
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _find(self):
        for i in range(10):
            cap = cv2.VideoCapture(i, self._backend)
            if cap.isOpened():
                ok, f = cap.read()
                cap.release()
                if ok and f is not None:
                    return i
        return 0

    def _loop(self):
        while self._running:
            ok, f = self.cap.read()
            if ok and f is not None:
                t = time.monotonic()
                with self._cond:
                    self._frame, self._t, self._seq = f, t, self._seq + 1
                    self._cond.notify_all()
            else:
                time.sleep(0.01)

    def wait_new(self, last_seq, timeout=1.0):
        """last_seq 이후의 새 프레임을 기다려 (frame, t, seq) 반환."""
        end = time.monotonic() + timeout
        with self._cond:
            while self._seq <= last_seq:
                left = end - time.monotonic()
                if left <= 0:
                    return None, 0.0, last_seq
                self._cond.wait(left)
            return self._frame, self._t, self._seq

    def has_ctrl(self, name):
        """시작할 때 v4l2 로 바꾼 컨트롤인지 (= 이 카메라에 있고, 종료 때 되돌릴 값이 있음)"""
        return any(n == name for n, _ in self._orig_ctrls)

    def set_ctrl(self, name, val):
        ok, _ = _v4l2(self.dev, f"--set-ctrl={name}={val}")
        return ok

    def release(self):
        self._running = False
        try:
            self.cap.release()
        except Exception:
            pass
        # 노출 설정을 원래대로 (자동 노출은 맨 마지막에 되돌려야 나머지 값이 들어감)
        for name, val in sorted(self._orig_ctrls, key=lambda c: c[0] == "auto_exposure"):
            _v4l2(self.dev, f"--set-ctrl={name}={val}")


FIXED_EXP, FIXED_GAIN = 130, 30      # 2026-11-20 실기 시험 D (고정 모드에서 안 준 쪽 값, 자동 모드 시작값)
AE_EXP_MIN = 78                      # 카메라 exposure_time_absolute 최솟값 (v4l2-ctl 확인)


def auto_bright_on(args):
    """--exposure / --cam-gain 을 둘 다 안 주면 자동 밝기 조절."""
    return args.exposure is None and args.cam_gain is None


def camera_start_values(args):
    """(노출, gain) 시작값. 노출 0 = 카메라 자동 노출, gain -1 = 그대로 둠."""
    if auto_bright_on(args):
        exp = max(AE_EXP_MIN, min(FIXED_EXP, args.ae_exp_max))
        return exp, max(0, min(FIXED_GAIN, args.ae_gain_max))
    exp = FIXED_EXP if args.exposure is None else args.exposure
    gain = FIXED_GAIN if args.cam_gain is None else args.cam_gain
    return exp, gain


def camera_ctrls(args):
    """명령줄 → v4l2 컨트롤 목록. --exposure 0 이면 노출은 건드리지 않음."""
    exp, gain = camera_start_values(args)
    c = []
    if exp > 0:
        # dynamic_framerate / auto_priority: 켜져 있으면 어두울 때 카메라가 fps 를 스스로 낮춤
        c += [("auto_exposure", 1), ("exposure_dynamic_framerate", 0), ("exposure_auto_priority", 0),
              ("exposure_time_absolute", exp)]
    if gain >= 0:
        c.append(("gain", gain))
    return c


class AutoBright:
    """0.5초마다 밝기를 재서 v4l2 노출(exposure_time_absolute)·gain 을 조금씩 조절.
    - 번짐을 막으려고 노출은 최대한 짧게:
        너무 밝음 → 노출을 AE_EXP_MIN(78)까지 먼저 줄이고, 그래도 밝으면 gain 을 0 까지
        너무 어두움 → gain 을 먼저 올리고(최대 gain_max), 그래도 어두우면 노출을 늘림(최대 exp_max)
    - 밝기 기준: 손이 검출되면 손바닥 영역 평균, 없으면 화면 전체 평균 + 하얗게 날아간 픽셀 비율.
      손을 놓친 직후(hold_s)는 바꾸지 않음 (손 기준 ↔ 화면 기준이 번갈아 가며 깜빡이는 것 방지).
    - 깜빡임 방지: 목표 ± band 안이면 안 바꿈, 한 번에 노출 ×1.12(멀면 ×1.25) / gain ±2(멀면 ±4).
    v4l2-ctl 호출은 이 스레드에서 하므로 검출 루프를 막지 않음."""
    CLIP_LEVEL = 250       # 이 값 이상 = 하얗게 날아간 픽셀
    CLIP_HAND = 0.08       # 손 영역에서 이 비율 넘게 날아가면 너무 밝음
    CLIP_FRAME = 0.05      # 화면 전체에서 이 비율 넘게 날아가면 너무 밝음
    CLIP_OK_TO_BRIGHTEN = 0.01   # 이미 날아간 픽셀이 이보다 많으면 밝게 하지 않음

    def __init__(self, cam, exp, gain, target=120.0, band=20.0, exp_min=AE_EXP_MIN, exp_max=130,
                 gain_max=40, period=0.5, hold_s=2.0):
        self.cam = cam
        self.exp, self.gain = int(exp), int(gain)
        self.target, self.band = float(target), float(band)
        self.exp_min, self.exp_max = int(exp_min), max(int(exp_min), int(exp_max))
        self.gain_max = int(gain_max)
        self.has_gain = cam.has_ctrl("gain")
        self.period, self.hold_s = period, hold_s
        self._frame = self._det = None
        self._t_hand = -1e9
        self.src, self.mean, self.clip = "-", 0.0, 0.0
        self.n_changes = 0
        self._stop = threading.Event()
        self._th = None

    @classmethod
    def create(cls, cam, args):
        """자동 조절을 쓸 수 있으면 객체, 아니면 None (이유 출력)."""
        has = getattr(cam, "has_ctrl", None)
        if has is None or not has("exposure_time_absolute"):
            print("[camera] 자동 밝기: 노출을 바꿀 수 없어 끔 (v4l2-ctl 없음 / 카메라가 지원 안 함)")
            return None
        exp, gain = camera_start_values(args)
        ab = cls(cam, exp, gain if has("gain") else 0, target=args.bright_target,
                 exp_max=args.ae_exp_max, gain_max=args.ae_gain_max)
        print(f"[camera] 자동 밝기: 켬 (목표 {ab.target:.0f}±{ab.band:.0f}, 노출 {ab.exp_min}~{ab.exp_max}, "
              f"gain 0~{ab.gain_max if ab.has_gain else '없음'}, 시작 {ab.exp}/{ab.gain})")
        return ab

    def observe(self, frame, det, t):
        """검출 루프에서 매 프레임 호출 (참조만 저장 — 가벼움)."""
        self._frame, self._det = frame, det
        if det is not None:
            self._t_hand = t

    @classmethod
    def measure(cls, frame, det):
        """반환 (기준, 평균 밝기 0~255, 날아간 픽셀 비율). 기준 = 'hand' | 'frame'.
        손 영역 = 손바닥 랜드마크(0,5,9,13,17) 상자의 가운데 70%."""
        if det is not None and len(det.get("pts") or ()) > 17:
            pp = [det["pts"][i] for i in HandDetector.PALM]
            h, w = frame.shape[:2]
            x0, x1 = min(p[0] for p in pp), max(p[0] for p in pp)
            y0, y1 = min(p[1] for p in pp), max(p[1] for p in pp)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            hw, hh = max(8, int((x1 - x0) * 0.35)), max(8, int((y1 - y0) * 0.35))   # 가운데 70% (가장자리 배경 제외)
            x0, x1 = max(0, cx - hw), min(w, cx + hw)
            y0, y1 = max(0, cy - hh), min(h, cy + hh)
            if x1 - x0 >= 8 and y1 - y0 >= 8:
                roi, src = frame[y0:y1, x0:x1], "hand"
            else:
                roi, src = frame[::4, ::4], "frame"
        else:
            roi, src = frame[::4, ::4], "frame"
        roi = np.ascontiguousarray(roi)
        g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        return src, float(g.mean()), float(np.count_nonzero(g >= cls.CLIP_LEVEL)) / g.size

    def decide(self, src, mean, clip):
        """측정값 → 새 (노출, gain). 바꿀 필요 없으면 지금 값 그대로."""
        exp, gain = self.exp, self.gain
        clip_lim = self.CLIP_HAND if src == "hand" else self.CLIP_FRAME
        err = mean - self.target
        too_bright = err > self.band or clip > clip_lim
        too_dark = err < -self.band and clip < self.CLIP_OK_TO_BRIGHTEN
        far = abs(err) > 2 * self.band or clip > 2 * clip_lim
        f, gs = (1.25, 4) if far else (1.12, 2)
        if too_bright:
            if exp > self.exp_min:
                exp = max(self.exp_min, min(exp - 2, int(round(exp / f))))
            elif self.has_gain and gain > 0:
                gain = max(0, gain - gs)
        elif too_dark:
            if self.has_gain and gain < self.gain_max:
                gain = min(self.gain_max, gain + gs)
            elif exp < self.exp_max:
                exp = min(self.exp_max, max(exp + 2, int(round(exp * f))))
        return exp, gain

    def step(self, now=None):
        frame, det = self._frame, self._det
        if frame is None:
            return
        now = time.monotonic() if now is None else now
        self.src, self.mean, self.clip = self.measure(frame, det)
        if det is None and now - self._t_hand < self.hold_s:
            self.src = "hold"                         # 손 놓친 직후 — 그대로 둠
            return
        exp, gain = self.decide(self.src, self.mean, self.clip)
        if exp != self.exp:
            if self.cam.set_ctrl("exposure_time_absolute", exp):
                self.exp = exp
                self.n_changes += 1
        if gain != self.gain:
            if self.cam.set_ctrl("gain", gain):
                self.gain = gain
                self.n_changes += 1

    def _loop(self):
        while not self._stop.wait(self.period):
            try:
                self.step()
            except Exception as e:                    # 밝기 조절 실패로 추적이 죽으면 안 됨
                print(f"\n[camera] 자동 밝기 오류: {e}")

    def start(self):
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()
        return self

    def stop(self):
        """카메라 설정을 되돌리기 전에 반드시 호출 (되돌린 뒤 다시 바꾸지 않게)."""
        self._stop.set()
        if self._th is not None:
            self._th.join(2.0)

    def status(self):
        return f"exp {self.exp:3d} gain {self.gain:2d} auto({self.src} {self.mean:3.0f})"


def camera_status_fixed(args):
    exp, gain = camera_start_values(args)
    e = "cam-auto" if exp <= 0 else f"{exp:3d}"
    g = "-" if gain < 0 else f"{gain:2d}"
    return f"exp {e} gain {g} fixed"


# ════════════════════════════════════════════════════════════════
# MediaPipe 손 검출: 손바닥 중심 = 손목 + 손가락 뿌리 4개 평균 (한 점보다 안정적)
# ════════════════════════════════════════════════════════════════
# ── 제스처: 주먹 = 따라가기, 손바닥(편 손) = 정지 ────────────────────
FINGERS = ((8, 6), (12, 10), (16, 14), (20, 18))   # (끝마디, 둘째마디) — 검지~새끼 (엄지는 제외)


def classify_pose(pts):
    """랜드마크 21개(픽셀) → 'FIST' | 'OPEN' | 'OTHER'.
    손가락 끝이 둘째마디보다 손목에서 멀면 '폄', 가까우면 '굽힘'. 회전/거리와 무관."""
    p = np.asarray(pts, dtype=np.float32)
    wrist = p[0]
    ext = curl = 0
    for tip, pip in FINGERS:
        r = np.linalg.norm(p[tip] - wrist) / max(1e-6, np.linalg.norm(p[pip] - wrist))
        if r > 1.15:
            ext += 1
        elif r < 1.0:
            curl += 1
    if ext >= 4:
        return "OPEN"
    if curl >= 3 and ext == 0:
        return "FIST"
    return "OTHER"


class GestureGate:
    """같은 제스처가 n 프레임 연속이어야 상태 전환 (깜빡임 방지).
    시작 상태는 STOP — 손을 보여도 주먹을 쥐기 전에는 움직이지 않음."""

    def __init__(self, n=3):
        self.n, self.state, self._cand, self._cnt = n, "STOP", None, 0

    def update(self, pose):
        want = {"FIST": "FOLLOW", "OPEN": "STOP"}.get(pose)
        if want is None or want == self.state:      # OTHER(애매) → 현재 상태 유지
            self._cand, self._cnt = None, 0
            return self.state, False
        if want == self._cand:
            self._cnt += 1
        else:
            self._cand, self._cnt = want, 1
        if self._cnt >= self.n:
            self.state, self._cand, self._cnt = want, None, 0
            return self.state, True
        return self.state, False

    def reset(self):
        self.state, self._cand, self._cnt = "STOP", None, 0


MODEL_PATH = os.path.join(HERE, "hand_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")


class HandDetector:
    """MediaPipe 버전에 따라 자동 선택:
       - 구버전(~0.10.1x): mp.solutions.hands  (기존 mediapipe_detector.py 와 같은 API)
       - 신버전(0.10.3x~): mp.tasks HandLandmarker (solutions 가 삭제됨, 모델 파일 필요)"""
    PALM = (0, 5, 9, 13, 17)

    def __init__(self, complexity=0, det_conf=0.6, trk_conf=0.5, proc_width=320, api="auto"):
        import mediapipe as mp
        self.mp = mp
        self.proc_width = proc_width
        use_legacy = hasattr(mp, "solutions") if api == "auto" else (api == "legacy")
        if use_legacy:
            self.api = "legacy"
            self.hands = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=1, model_complexity=complexity,
                min_detection_confidence=det_conf, min_tracking_confidence=trk_conf)
        else:
            self.api = "tasks"
            from mediapipe.tasks.python import BaseOptions, vision
            opts = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=self._model()),
                running_mode=vision.RunningMode.VIDEO, num_hands=1,
                min_hand_detection_confidence=det_conf, min_hand_presence_confidence=det_conf,
                min_tracking_confidence=trk_conf)
            self.hands = vision.HandLandmarker.create_from_options(opts)
            self._ts = 0
        print(f"[mediapipe] {getattr(mp, '__version__', '?')} ({self.api} API)")

    @staticmethod
    def _model():
        if not os.path.exists(MODEL_PATH):
            import urllib.request
            print(f"[mediapipe] 손 모델 다운로드 중... ({MODEL_URL})")
            tmp = MODEL_PATH + ".part"
            urllib.request.urlretrieve(MODEL_URL, tmp)
            os.replace(tmp, MODEL_PATH)
        return MODEL_PATH

    def detect(self, frame):
        h, w = frame.shape[:2]
        if self.proc_width and w > self.proc_width:
            small = cv2.resize(frame, (self.proc_width, int(h * self.proc_width / w)),
                               interpolation=cv2.INTER_AREA)
        else:
            small = frame
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        if self.api == "legacy":
            rgb.flags.writeable = False
            res = self.hands.process(rgb)
            if not res.multi_hand_landmarks:
                return None
            lm = res.multi_hand_landmarks[0].landmark
            score = res.multi_handedness[0].classification[0].score if res.multi_handedness else 1.0
        else:
            self._ts = max(self._ts + 1, int(time.monotonic() * 1000))   # 단조 증가 필수
            img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            res = self.hands.detect_for_video(img, self._ts)
            if not res.hand_landmarks:
                return None
            lm = res.hand_landmarks[0]
            score = res.handedness[0][0].score if res.handedness else 1.0
        cx = float(np.mean([lm[i].x for i in self.PALM])) * w
        cy = float(np.mean([lm[i].y for i in self.PALM])) * h
        pts = [(int(p.x * w), int(p.y * h)) for p in lm]
        pose = classify_pose([(p.x * w, p.y * h) for p in lm])
        return {"cx": cx, "cy": cy, "w": w, "h": h, "score": float(score), "pts": pts,
                "pose": pose}

    def close(self):
        try:
            self.hands.close()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
# 제어 수학 (하드웨어 독립 — 시뮬레이션 테스트 대상)
# ════════════════════════════════════════════════════════════════
class SafetyLimits:
    """하드웨어 안전 리밋 — 기존 조이스틱(routes/core.py)과 같은 규칙, 물리 각도 기준.
    (.agents/rules/hardware-safety.md)
      M1(Pan) ±180°, M2(Tilt) 위 +50° / 아래 -40°
      카메라가 -25° 보다 아래를 보면 M1 ±80° (기둥 충돌 방지)
      M1 이 ±80° 를 넘으면 M2 는 -25° 까지만
      + 웹에서 설정한 사용자 리밋(state.soft_limit_*), + 경계 여유 margin°
    펌웨어 단위(POS 값) ↔ 물리 각도 변환은 state.py 실측값을 그대로 사용."""

    def __init__(self, st=None, margin=2.0):
        if st is None:
            try:
                import state as st
            except ImportError:
                st = None
        self.st, self.margin = st, margin
        g = lambda k, d: getattr(st, k, d) if st is not None else d
        self.k1 = g("_M1_PHYS_TO_ESP32", 22.7 / 180.0)
        self.up_e, self.up_p = abs(g("_M2_ESP32_AT_UP", -6.5)), g("_M2_PHYS_AT_UP", 50.0)
        self.dn_e, self.dn_p = abs(g("_M2_ESP32_AT_DOWN", 4.0)), g("_M2_PHYS_AT_DOWN", 40.0)

    def m1_phys(self, fw):
        return fw / self.k1

    def m1_fw(self, p):
        return p * self.k1

    def m2_phys(self, fw):          # 펌웨어 음수 = 위(+), 양수 = 아래(-)
        return -fw * (self.up_p / self.up_e) if fw < 0 else -fw * (self.dn_p / self.dn_e)

    def m2_fw(self, p):
        return -p * (self.up_e / self.up_p) if p > 0 else -p * (self.dn_e / self.dn_p)

    def clamp(self, a1, a2, cur=None):
        """목표 (a1, a2)[펌웨어 단위] → 안전 범위로 자른 값. cur(현재 위치)도 함께 보고 더 엄격하게."""
        m = self.margin
        p1, p2 = self.m1_phys(a1), self.m2_phys(a2)
        c1, c2 = (self.m1_phys(cur[0]), self.m2_phys(cur[1])) if cur else (p1, p2)
        down = min(p2, c2) < -25.0 + m
        m1_lim = (80.0 if down else 180.0) - m
        m1_max, m1_min = m1_lim, -m1_lim
        m2_max = 50.0 - m
        st = self.st
        if st is not None:
            if getattr(st, "soft_limit_m1_max", None) is not None:
                m1_max = min(m1_max, self.m1_phys(st.soft_limit_m1_max) - m)
            if getattr(st, "soft_limit_m1_min", None) is not None:
                m1_min = max(m1_min, self.m1_phys(st.soft_limit_m1_min) + m)
        p1 = max(m1_min, min(m1_max, p1))
        wide = max(abs(p1), abs(c1)) > 80.0 - m
        m2_min = (-25.0 if wide else -40.0) + m
        if st is not None:
            if getattr(st, "soft_limit_m2_min", None) is not None:      # 펌웨어 음수 쪽 = 위 한계
                m2_max = min(m2_max, self.m2_phys(st.soft_limit_m2_min) - m)
            if getattr(st, "soft_limit_m2_max", None) is not None:      # 펌웨어 양수 쪽 = 아래 한계
                m2_min = max(m2_min, self.m2_phys(st.soft_limit_m2_max) + m)
        p2 = max(m2_min, min(m2_max, p2))
        return self.m1_fw(p1), self.m2_fw(p2)


class AlphaBeta:
    """1축 알파-베타 필터 (위치 + 속도). 시간 간격(dt) 가변."""

    def __init__(self, alpha=0.6, beta=0.12, vmax=150.0):
        self.alpha, self.beta, self.vmax = alpha, beta, vmax
        self.x = self.v = self.t = 0.0
        self.ready = False

    def reset(self, x, t):
        self.x, self.v, self.t, self.ready = x, 0.0, t, True

    def update(self, z, t):
        if not self.ready:
            self.reset(z, t)
            return
        dt = max(1e-3, t - self.t)
        xp = self.x + self.v * dt
        r = z - xp
        self.x = xp + self.alpha * r
        self.v = max(-self.vmax, min(self.vmax, self.v + self.beta * r / dt))
        self.t = t

    def predict(self, t):
        return self.x + self.v * (t - self.t)


class PoseHistory:
    """(시각, M1, M2) 기록 → 프레임 촬영 시각의 모터 위치를 보간."""

    def __init__(self, maxlen=400):
        self._buf = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, t, m1, m2):
        with self._lock:
            if not self._buf or (self._buf[-1][1], self._buf[-1][2]) != (m1, m2) \
                    or t - self._buf[-1][0] > 0.05:
                self._buf.append((t, m1, m2))

    def at(self, t):
        with self._lock:
            if not self._buf:
                return None
            if t <= self._buf[0][0]:
                return self._buf[0][1:]
            prev = self._buf[0]
            for cur in self._buf:
                if cur[0] >= t:
                    span = cur[0] - prev[0]
                    k = 0.0 if span <= 0 else (t - prev[0]) / span
                    return (prev[1] + k * (cur[1] - prev[1]),
                            prev[2] + k * (cur[2] - prev[2]))
                prev = cur
            return self._buf[-1][1:]


class Tracker:
    """검출 결과 → 절대 목표 각도 → 필터 → (지연 보상) 명령 각도.

    2026-11-20 변경 (손을 놓칠 때 '휙' 밀리던 문제):
      예전: 제어 스레드가 50Hz 로 '필터 위치 + 속도 × (경과시간 + lead)' 를 계속 다시 계산해서 보냄.
            검출이 없어도 목표가 마지막 속도 방향으로 계속 밀려 나갔고(최대 0.37초 분량,
            속도 상한 150°/s), 그래서 LOST 중에도 cmd 34/s, TRACK 중 cmd > det 였음.
      지금: ① 새 검출이 들어왔을 때만 목표를 한 번 계산 (cmd/s ≤ det/s)
            ② 목표 = 그 프레임을 찍은 순간의 모터 위치(POS 기록 보간) + 오차 × 게인 (+ 제한된 예측)
            ③ 마지막 검출 후 lost_stop 초(기본 0.2) 지나면 S 로 정지
            ④ 한 프레임 만에 너무 크게 튄 검출은 무시 (2번 연속까지)
            ⑤ 명령 한 번에 현재 위치에서 max_step 이상 떨어진 목표는 보내지 않음"""

    def __init__(self, k1, k2, alpha=0.6, beta=0.12, lead=0.12, deadzone_px=6.0,
                 lost_stop=0.2, lost_reset=1.0, cam_latency=0.04, jump_px=150.0,
                 max_step=None, max_lead_px=40.0, limits=None):
        self.k1, self.k2 = k1, k2              # 오차 1px(640 기준) 당 각도 (부호 포함)
        self.f1, self.f2 = AlphaBeta(alpha, beta), AlphaBeta(alpha, beta)
        self.lead, self.deadzone = lead, deadzone_px
        self.lost_stop, self.lost_reset = lost_stop, lost_reset
        self.cam_latency, self.jump_px = cam_latency, jump_px
        # 명령 1번 최대 이동 [펌웨어 °]. 지정 안 하면 화면 200px 에 해당하는 각도
        if max_step is None:
            self.max_step = (200.0 * abs(k1), 200.0 * abs(k2))
        else:
            self.max_step = (float(max_step), float(max_step))
        self.max_lead = (max_lead_px * abs(k1), max_lead_px * abs(k2))
        self.last_det_t = None
        self.last_err = (0.0, 0.0)
        self.history = PoseHistory()
        self.limits = limits or SafetyLimits()
        self._lock = threading.Lock()
        self._stop_pending = False
        self._target = None                    # 마지막 검출로 계산한 목표 (펌웨어 °)
        self._tseq = self._sent_seq = 0
        self._rejects = 0
        self._lost_sent = True
        self.n_rejected = 0                    # 통계: 튐으로 버린 검출 수

    def _clear(self):
        self.f1.ready = self.f2.ready = False
        self.last_det_t = None
        self._target = None
        self._rejects = 0

    def halt(self):
        """즉시 정지 요청 (손바닥/손 사라짐). 제어 스레드가 S 를 보내고 필터를 비움."""
        with self._lock:
            self._clear()
            self._lost_sent = True
            self._stop_pending = True

    def pop_stop(self):
        with self._lock:
            s, self._stop_pending = self._stop_pending, False
            return s

    def on_detection(self, det, t_frame, now=None):
        """새 검출 1개 → 목표를 한 번 새로 계산. 버렸으면 False."""
        now = time.monotonic() if now is None else now
        ex = (det["cx"] - det["w"] / 2.0) * REF_W / det["w"]
        ey = (det["cy"] - det["h"] / 2.0) * REF_H / det["h"]
        self.last_err = (ex, ey)
        pose = self.history.at(t_frame - self.cam_latency)   # 촬영 순간의 모터 위치
        if pose is None:
            return False
        if abs(ex) < self.deadzone:
            ex = 0.0
        if abs(ey) < self.deadzone:
            ey = 0.0
        z1 = pose[0] + self.k1 * ex            # 손의 절대 각도 (펌웨어 °)
        z2 = pose[1] + self.k2 * ey
        with self._lock:
            stale = self.last_det_t is None or not self.f1.ready \
                or (t_frame - self.last_det_t) > self.lost_reset
            reset = stale
            if not stale:
                # 직전 추정에서 화면 몇 px 만큼 튀었나 (모터가 돈 만큼은 이미 빠진 값)
                d = max(abs(z1 - self.f1.predict(t_frame)) / max(abs(self.k1), 1e-9),
                        abs(z2 - self.f2.predict(t_frame)) / max(abs(self.k2), 1e-9))
                if d > self.jump_px:
                    if self._rejects < 2:
                        self._rejects += 1
                        self.n_rejected += 1
                        return False
                    reset = True               # 3번 연속 같은 쪽이면 진짜 이동으로 보고 받아들임
            self._rejects = 0
            if reset:
                self.f1.reset(z1, t_frame)
                self.f2.reset(z2, t_frame)
            else:
                self.f1.update(z1, t_frame)
                self.f2.update(z2, t_frame)
            self.last_det_t = t_frame
            # 예측: 지금까지 지난 시간 + lead 만큼, 단 화면 max_lead_px 이내로만
            ahead = self.lead + max(0.0, now - t_frame)
            l1 = max(-self.max_lead[0], min(self.max_lead[0], self.f1.v * ahead))
            l2 = max(-self.max_lead[1], min(self.max_lead[1], self.f2.v * ahead))
            self._target = (self.f1.x + l1, self.f2.x + l2)
            self._tseq += 1
            self._lost_sent = False
            return True

    def next_command(self, now, cur):
        """제어 스레드용. 반환 (목표 또는 None, S 를 보내야 하나).
        목표는 새 검출이 있을 때 1번만 나옴 + 한 번 이동량 제한 + 안전 리밋."""
        with self._lock:
            if self.last_det_t is None or self._target is None:
                return None, False
            since = now - self.last_det_t
            if since > self.lost_reset:
                self._clear()
            if since > self.lost_stop:
                if not self._lost_sent:        # 놓친 뒤 lost_stop 초 → 그 자리 정지 (1번만)
                    self._lost_sent = True
                    return None, True
                return None, False
            if self._tseq == self._sent_seq:
                return None, False
            self._sent_seq = self._tseq
            t1, t2 = self._target
        t1 = cur[0] + max(-self.max_step[0], min(self.max_step[0], t1 - cur[0]))
        t2 = cur[1] + max(-self.max_step[1], min(self.max_step[1], t2 - cur[1]))
        return self.limits.clamp(t1, t2, cur), False

    def tracking(self, now):
        return self.last_det_t is not None and (now - self.last_det_t) <= self.lost_stop


# ════════════════════════════════════════════════════════════════
# 모터: 기존 motor_esp32.py 를 그대로 사용 (수정 없음)
# ════════════════════════════════════════════════════════════════
class Motor:
    """msl: 최대 속도 [Hz], acc: 가속도 [CFG 값 = Hz/ms × 10].
    motor_esp32.connect() 는 연결(재연결 포함)할 때마다 state.esp32_max_speed_hz /
    esp32_accel_rate 를 CFG:MSL / CFG:ACC 로 보냄 → 그 state 값만 바꿔 두면
    ESP32 가 재시작돼도 매번 우리 값이 들어감 (motor_esp32.py 수정 없음)."""

    def __init__(self, port=None, msl=None, acc=None):
        import state
        import motor_esp32
        self.state, self.m = state, motor_esp32
        self.pos_event = threading.Event()
        self.on_pos = None                         # (t, m1, m2) 콜백 — POS 받은 시각 그대로 기록
        self.cfg_ack = {}                          # ESP32 가 'OK CFG:KEY:VAL' 로 확인한 값
        self.ready = False                         # 시작 확인이 끝난 뒤 True
        self.rebooted = False                      # 실행 중 ESP32 재시작 감지 → 위치 기준이 0 으로 바뀜
        if msl is not None:
            state.esp32_max_speed_hz = float(msl)
        if acc is not None:
            state.esp32_accel_rate = float(acc) / 10.0
        orig = motor_esp32._parse_status

        def _quiet_parse(line):
            # MOVE 응답이 초당 수십 줄 찍히지 않게 걸러냄 + POS 수신 시각 기록
            if line.startswith("OK MOVE"):
                return
            if line.startswith("OK CFG:"):
                k, _, v = line[7:].partition(":")
                self.cfg_ack[k.strip().upper()] = v.strip()
                return
            if line.startswith("OK BOOT") and self.ready:
                self.rebooted = True
                self.send_cfg()                    # 펌웨어 기본값으로 돌아갔으니 다시 보냄
            orig(line)
            if line.startswith("POS:"):
                if self.on_pos is not None:
                    self.on_pos(time.monotonic(), state.esp32_pos_m1_deg, state.esp32_pos_m2_deg)
                self.pos_event.set()

        motor_esp32._parse_status = _quiet_parse   # 모듈 내부 호출을 가로챔 (파일은 그대로)
        state.device_type = "esp32"
        state.control_mode = "manual"              # → 기존 루프가 POS 모드 유지, T 전송 안 함
        motor_esp32.start(port)

    def cfg_wanted(self):
        return {"MSL": str(int(self.state.esp32_max_speed_hz)),
                "ACC": str(int(self.state.esp32_accel_rate * 10))}

    def send_cfg(self):
        for k, v in self.cfg_wanted().items():
            self.m.send_config(k, v)

    def confirm_cfg(self, timeout=1.0):
        """CFG 가 ESP32 에 들어갔는지 응답으로 확인. 안 들어갔으면 한 번 더 보냄."""
        want = self.cfg_wanted()
        for attempt in range(2):
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                if all(self.cfg_ack.get(k) == v for k, v in want.items()):
                    return True
                time.sleep(0.05)
            if attempt == 0:
                self.cfg_ack.clear()
                self.send_cfg()
        return False

    @property
    def connected(self):
        return bool(self.state.motor_connected)

    def pos(self):
        return self.state.esp32_pos_m1_deg, self.state.esp32_pos_m2_deg

    def speeds(self):
        return self.state.esp32_speed_m1, self.state.esp32_speed_m2

    def move_abs(self, a1, a2):
        self.m._send(f"MOVE J XY {a1:.3f} {a2:.3f}\n")

    def stop(self):
        self.m._send("S\n")

    def release(self):
        try:
            self.m.release_motors()
        except Exception:
            pass

    def default_gains(self):
        # 펌웨어 T 경로와 같은 환산: 1px = STEPS_PER_PIX / STEPS_PER_DEG [펌웨어 각도]
        spx = float(self.state.motor_steps_per_px)
        return spx / float(self.state.esp32_steps_per_deg_m1), \
            spx / float(self.state.esp32_steps_per_deg_m2)


# ════════════════════════════════════════════════════════════════
# 미리보기 MJPEG 서버 (접속자가 있을 때만 인코딩)
# ════════════════════════════════════════════════════════════════
class Preview:
    def __init__(self, port):
        self._jpg = None
        self._cond = threading.Condition()
        self.clients = 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path not in ("/", "/stream"):
                    self.send_error(404)
                    return
                if self.path == "/":
                    body = (b"<html><body style='margin:0;background:#111'>"
                            b"<img src='/stream' style='width:100%;max-width:960px'></body></html>")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f")
                self.end_headers()
                outer.clients += 1
                try:
                    while True:
                        with outer._cond:
                            outer._cond.wait(1.0)
                            jpg = outer._jpg
                        if jpg is None:
                            continue
                        self.wfile.write(b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    outer.clients -= 1

        self.server = ThreadingHTTPServer(("0.0.0.0", port), H)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def push(self, frame):
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if ok:
            with self._cond:
                self._jpg = buf.tobytes()
                self._cond.notify_all()


def draw_overlay(frame, det, tracker, info):
    h, w = frame.shape[:2]
    cv2.drawMarker(frame, (w // 2, h // 2), (255, 255, 255), cv2.MARKER_CROSS, 24, 1)
    if det:
        for p in det["pts"]:
            cv2.circle(frame, p, 2, (0, 200, 255), -1)
        cv2.circle(frame, (int(det["cx"]), int(det["cy"])), 9, (0, 255, 0), 2)
        cv2.line(frame, (w // 2, h // 2), (int(det["cx"]), int(det["cy"])), (0, 255, 0), 1)
    color = (0, 255, 0) if info.get("tracking") else (0, 165, 255)
    cv2.putText(frame, info.get("text", ""), (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    return frame


# ════════════════════════════════════════════════════════════════
# 캘리브레이션: 모터를 조금 움직이고 화면이 몇 px 밀리는지 위상상관으로 측정
# ════════════════════════════════════════════════════════════════
def _gray(frame):
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return np.float32(g)


def _wait_settle(motor, a1, a2, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        p1, p2 = motor.pos()
        s1, s2 = motor.speeds()
        if abs(p1 - a1) < 0.05 and abs(p2 - a2) < 0.05 and abs(s1) < 1 and abs(s2) < 1:   # 1스텝≈0.0225°
            return True
        time.sleep(0.02)
    return False


def _fresh_frame(cam, settle=0.35):
    time.sleep(settle)
    _, _, seq = cam.wait_new(0, 1.0)
    for _ in range(3):   # 버퍼에 남은 이전 장면 버리기
        frame, _, seq = cam.wait_new(seq, 1.0)
    return frame


def calibrate(motor, cam, step=1.0, limits=None):
    limits = limits or SafetyLimits(motor.state)
    base1, base2 = motor.pos()
    print(f"[calib] 시작 위치 M1={base1:.2f} M2={base2:.2f}, 스텝 ±{step}")
    print("[calib] 무늬가 있는 배경을 향하게 두고, 화면 안에서 움직이는 것이 없게 해 주세요.")
    win = None
    gains = {}
    for axis in (1, 2):
        samples = []
        for sign in (+1, -1):
            motor.move_abs(base1, base2)
            _wait_settle(motor, base1, base2)
            ref = _fresh_frame(cam)
            t1 = base1 + (sign * step if axis == 1 else 0.0)
            t2 = base2 + (sign * step if axis == 2 else 0.0)
            t1, t2 = limits.clamp(t1, t2, (base1, base2))
            delta = (t1 - base1) if axis == 1 else (t2 - base2)
            if abs(delta) < 0.3 * step:
                print(f"[calib] M{axis} {sign:+d} 방향은 안전 리밋에 막혀 건너뜀")
                continue
            motor.move_abs(t1, t2)
            if not _wait_settle(motor, t1, t2):
                print(f"[calib] M{axis} 이동이 끝나지 않았습니다 (위치 피드백 확인 필요)")
            img = _fresh_frame(cam)
            a, b = _gray(ref), _gray(img)
            if win is None:
                win = cv2.createHanningWindow(a.shape[::-1], cv2.CV_32F)
            (dx, dy), resp = cv2.phaseCorrelate(a, b, win)
            h, w = a.shape
            shift = (dx * REF_W / w) if axis == 1 else (dy * REF_H / h)
            print(f"[calib] M{axis} {delta:+.2f}° → 화면 이동 dx={dx:+.1f} dy={dy:+.1f}px "
                  f"(신뢰도 {resp:.2f})")
            if resp < 0.05:
                print("[calib]   ⚠ 신뢰도가 낮습니다 — 무늬 있는 배경에서 다시 해 보세요")
            samples.append(shift / delta)
        motor.move_abs(base1, base2)
        _wait_settle(motor, base1, base2)
        if not samples:
            print(f"[calib] M{axis}: 안전 범위 안에서 움직일 수 없습니다. 중앙 쪽으로 옮긴 뒤 다시 하세요.")
            return None
        g = float(np.mean(samples))          # +1° 당 화면 이동 px (640 기준)
        if abs(g) < 0.2:
            print(f"[calib] M{axis}: 화면이 거의 안 움직였습니다. 실패.")
            return None
        gains[axis] = -1.0 / g               # 오차 1px 를 없애려면 몇 ° 움직여야 하나
    d1, d2 = motor.default_gains()
    print(f"[calib] 측정 게인  k1={gains[1]:+.5f}  k2={gains[2]:+.5f}  (°/px)")
    print(f"[calib] 기존 펌웨어 환산 k1={d1:+.5f}  k2={d2:+.5f}  "
          f"→ 비율 {gains[1] / d1:.2f}x, {gains[2] / d2:.2f}x")
    data = {"k1": gains[1], "k2": gains[2], "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "step": step, "width": cam.w, "height": cam.h}
    with open(CALIB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[calib] 저장: {CALIB_PATH}")
    return data


def load_gains(motor, args):
    if args.k1 is not None and args.k2 is not None:
        return args.k1, args.k2, "명령줄"
    try:
        with open(CALIB_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return float(d["k1"]), float(d["k2"]), f"캘리브레이션 ({d.get('time', '?')})"
    except (OSError, ValueError, KeyError):
        pass
    if motor is not None:
        k1, k2 = motor.default_gains()
    else:
        k1 = k2 = 3.5 / 44.44
    return k1, k2, "펌웨어 기본값 (--calibrate 권장)"


# ════════════════════════════════════════════════════════════════
# 실행
# ════════════════════════════════════════════════════════════════
def port_in_use(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def control_loop(motor, tracker, stop_evt, hz=50.0, min_step=0.02, stats=None):
    """새 목표가 생겼을 때만 MOVE 를 보냄. 정지 요청/손 놓침 → S.
    (모터 위치 기록은 POS 를 받을 때 Motor.on_pos 가 함)"""
    last = None
    period = 1.0 / hz
    while not stop_evt.is_set():
        now = time.monotonic()
        if motor.connected:
            p1, p2 = motor.pos()
            if motor.on_pos is None:
                tracker.history.add(now, p1, p2)
            if motor.rebooted:                 # 위치 기준을 믿을 수 없음 → 아무것도 안 보냄
                tracker.pop_stop()
                time.sleep(period)
                continue
            stop = tracker.pop_stop()
            cmd, lost = tracker.next_command(now, (p1, p2))
            if stop or lost:
                motor.stop()
                last = None
                if stats is not None:
                    stats["stops"] = stats.get("stops", 0) + 1
            elif cmd is not None and (last is None or abs(cmd[0] - last[0]) > min_step
                                      or abs(cmd[1] - last[1]) > min_step):
                motor.move_abs(*cmd)
                last = cmd
                if stats is not None:
                    stats["sent"] += 1
        time.sleep(max(0.0, period - (time.monotonic() - now)))


def run(args, cam=None, detector=None, motor=None, duration=None, on_frame=None):
    """duration/on_frame/주입 객체는 시뮬레이션 테스트용."""
    if motor is None and not args.no_motor:
        if port_in_use(5000) and not args.force:
            print("❌ 포트 5000 이 사용 중입니다 — main.py(웹 대시보드)가 켜져 있는 것 같습니다.")
            print("   카메라와 ESP32 시리얼을 같이 쓸 수 없으니 main.py 를 먼저 종료하세요.")
            print("   (무시하고 실행: --force)")
            return 1
        motor = Motor(args.port, msl=args.msl, acc=args.acc)
    if motor is not None:
        print("[motor] ESP32 위치 피드백 대기...")
        if not motor.pos_event.wait(8.0):
            print("❌ ESP32 위치 피드백(POS)이 오지 않습니다. USB 연결/전원을 확인하세요.")
            return 1
        w = motor.cfg_wanted()
        if motor.confirm_cfg():
            print(f"[motor] 속도 설정 확인: MSL {w['MSL']}Hz, ACC {int(w['ACC']) / 10:.1f}Hz/ms (ESP32 응답 OK)")
        else:
            print(f"⚠ ESP32 가 속도 설정(MSL {w['MSL']}, ACC {w['ACC']})에 응답하지 않았습니다. 받은 값: {motor.cfg_ack}")
        motor.ready = True
        p1, p2 = motor.pos()
        lim = SafetyLimits(motor.state)
        print(f"[motor] 연결됨, 현재 M1={p1:.2f} M2={p2:.2f} (물리 약 {lim.m1_phys(p1):+.0f}°, {lim.m2_phys(p2):+.0f}°)")
        if lim.clamp(p1, p2, (p1, p2)) != (p1, p2):
            print("⚠ 현재 위치가 안전 범위 경계 밖/근처입니다. 목표는 안전 범위로만 보냅니다.")

    if cam is None:
        try:
            cam = Camera(args.camera, args.width, args.height, args.cam_fps, camera_ctrls(args))
        except RuntimeError as e:
            print(f"❌ {e} — 카메라 연결을 확인하거나 --camera 로 번호를 지정하세요.")
            if motor is not None:
                motor.stop()
                motor.release()
            return 1

    if args.calibrate:
        if motor is None:
            print("❌ 캘리브레이션에는 모터가 필요합니다")
            return 1
        ok = calibrate(motor, cam, args.calib_step, SafetyLimits(motor.state))
        return 0 if ok else 1

    k1, k2, src = load_gains(motor, args)
    print(f"[track] 게인 k1={k1:+.5f} k2={k2:+.5f} °/px  ← {src}")
    lim = SafetyLimits(motor.state if motor is not None else None)
    tracker = Tracker(k1 * args.gain, k2 * args.gain, alpha=args.alpha, beta=args.beta,
                      lead=args.lead, deadzone_px=args.deadzone, lost_stop=args.lost_stop,
                      cam_latency=args.cam_latency, jump_px=args.jump_px,
                      max_step=args.max_step, max_lead_px=args.max_lead_px, limits=lim)
    ms1, ms2 = tracker.max_step
    print(f"[track] 명령 1번 최대 이동 M1 {ms1:.2f}° (물리 약 {abs(lim.m1_phys(ms1)):.0f}°)  "
          f"M2 {ms2:.2f}° (물리 약 {abs(lim.m2_phys(ms2)):.0f}°)   "
          f"손 놓치면 {args.lost_stop:.2f}s 뒤 정지   튐 무시 > {args.jump_px:.0f}px")
    if motor is not None:
        motor.on_pos = tracker.history.add    # POS 받은 시각으로 모터 위치 기록

    if detector is None:
        print("[track] MediaPipe 로딩...")
        detector = HandDetector(complexity=args.complexity, proc_width=args.proc_width,
                                api=args.mp_api)

    preview = None
    if args.preview_port:
        try:
            preview = Preview(args.preview_port)
            print(f"[preview] http://<파이주소>:{args.preview_port}/")
        except OSError as e:
            print(f"[preview] 시작 실패: {e}")

    ab = AutoBright.create(cam, args) if auto_bright_on(args) else None
    cam_txt_fixed = camera_status_fixed(args)
    if ab is None and not auto_bright_on(args):
        print(f"[camera] 자동 밝기: 끔 ({cam_txt_fixed})")
    if ab is not None:
        ab.start()

    if motor is None:
        tracker.history.add(time.monotonic(), 0.0, 0.0)   # 모터 없음: 위치 0 고정으로 상태만 표시
    stop_evt = threading.Event()
    stats = {"sent": 0}
    if motor is not None:
        threading.Thread(target=control_loop, args=(motor, tracker, stop_evt),
                         kwargs={"hz": args.rate, "stats": stats}, daemon=True).start()

    gate = GestureGate(args.gesture_frames) if args.gesture == "fist" else None
    last_seen = time.monotonic()
    if gate:
        print("✊ 주먹 = 따라가기   ✋ 손바닥 = 정지   (시작은 정지 상태)")
    print("✅ 손 추적 시작 (Ctrl+C 로 종료)")
    seq, n_frames, n_det, t0 = 0, 0, 0, time.monotonic()
    t_start = t0
    fps = det_rate = cam_fps = 0.0
    seq0 = 0
    reboot_warned = False
    try:
        while True:
            if duration is not None and time.monotonic() - t_start > duration:
                break
            frame, t_frame, seq = cam.wait_new(seq, 1.0)
            if frame is None:
                continue
            det = detector.detect(frame)
            n_frames += 1
            if det is not None and det.get("score", 1.0) >= args.min_score:
                n_det += 1
                last_seen = t_frame
                if gate is None:
                    tracker.on_detection(det, t_frame, time.monotonic())
                else:
                    g, changed = gate.update(det.get("pose"))
                    if changed:
                        print(f"\n[gesture] {'✊ 따라가기' if g == 'FOLLOW' else '✋ 정지'}")
                        if g == "STOP":
                            tracker.halt()
                    if g == "FOLLOW":
                        tracker.on_detection(det, t_frame, time.monotonic())
                    else:
                        tracker.last_err = ((det["cx"] - det["w"] / 2) * REF_W / det["w"],
                                            (det["cy"] - det["h"] / 2) * REF_H / det["h"])
            else:
                det = None
                # 손이 1초 넘게 안 보이면 다시 '정지' 상태로 (다시 주먹을 쥐어야 출발)
                if gate is not None and gate.state == "FOLLOW" and t_frame - last_seen > 1.0:
                    gate.reset()
                    tracker.halt()
                    print("\n[gesture] 손 사라짐 → ✋ 정지 (다시 주먹을 쥐면 출발)")
            if ab is not None:
                ab.observe(frame, det, t_frame)
            if on_frame:
                on_frame(det, t_frame)
            if motor is not None and motor.rebooted and not reboot_warned:
                reboot_warned = True
                tracker.halt()
                print("\n⚠ ESP32 가 실행 중에 재시작됐습니다 (전원 흔들림/USB 재연결?). 위치 기준이 0 으로 바뀌어서"
                      "\n  안전 리밋을 믿을 수 없으므로 추적을 멈췄습니다. 터렛을 가운데로 놓고 다시 실행하세요.")

            now = time.monotonic()
            if now - t0 >= 1.0:
                fps, det_rate = n_frames / (now - t0), n_det / (now - t0)
                cam_fps = (seq - seq0) / (now - t0)
                seq0 = seq
                n_frames = n_det = 0
                t0 = now
                ex, ey = tracker.last_err
                p = motor.pos() if motor is not None else (0.0, 0.0)
                if gate is not None and gate.state == "STOP":
                    state_txt = "STOP "
                else:
                    state_txt = "TRACK" if tracker.tracking(now) else "LOST "
                line = (f"{state_txt} cam {cam_fps:4.1f} fps {fps:4.1f} det {det_rate:4.1f}/s  "
                        f"err ({ex:+6.1f},{ey:+6.1f})px  M1 {p[0]:+7.2f} M2 {p[1]:+7.2f}  "
                        f"cmd {stats['sent']}/s stop {stats.get('stops', 0)} skip {tracker.n_rejected}  "
                        f"{ab.status() if ab is not None else cam_txt_fixed}")
                stats["sent"] = 0
                stats["stops"] = 0
                tracker.n_rejected = 0
                print("\r" + line, end="", flush=True)

            if preview is not None and preview.clients > 0:
                if gate is not None and gate.state == "STOP":
                    mode = "STOP (open palm)"
                elif gate is not None:
                    mode = "FOLLOW (fist)" if tracker.tracking(now) else "FOLLOW - lost"
                else:
                    mode = "TRACK" if tracker.tracking(now) else "LOST"
                pose = det.get("pose", "") if det else "-"
                txt = f"{mode}  [{pose}]  {fps:.1f}fps"
                if ab is not None:
                    txt += f"  exp {ab.exp} g {ab.gain}"
                following = tracker.tracking(now) and (gate is None or gate.state == "FOLLOW")
                vis = draw_overlay(frame.copy(), det, tracker,
                                   {"text": txt, "tracking": following})
                preview.push(vis)
    except KeyboardInterrupt:
        print("\n[track] 종료 중...")
    finally:
        stop_evt.set()
        if ab is not None:
            ab.stop()          # 카메라 설정을 되돌리기 전에 자동 밝기 스레드부터 멈춤
        time.sleep(0.05)
        if motor is not None:
            motor.stop()
            if not args.hold:
                motor.release()
        try:
            detector.close()
        except Exception:
            pass
        try:
            cam.release()
        except Exception:
            pass
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="MediaPipe 손 추적 단독 실행기 (ESP32 터렛)")
    p.add_argument("--calibrate", action="store_true", help="카메라-모터 게인 자동 측정 후 저장")
    p.add_argument("--calib-step", type=float, default=1.0, help="캘리브레이션 이동량 [펌웨어 °]")
    p.add_argument("--no-motor", action="store_true", help="모터 없이 검출/미리보기만")
    p.add_argument("--force", action="store_true", help="main.py 실행 중이어도 강행")
    p.add_argument("--port", help="ESP32 시리얼 포트 (기본: 자동)")
    p.add_argument("--camera", type=int, help="카메라 index (기본: 자동)")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--proc-width", type=int, default=320, help="MediaPipe 입력 폭 (작을수록 빠름)")
    p.add_argument("--complexity", type=int, default=0, choices=(0, 1), help="0=빠름, 1=정확")
    p.add_argument("--mp-api", default="auto", choices=("auto", "legacy", "tasks"),
                   help="MediaPipe API (auto: 설치된 버전에 맞춰 선택)")
    p.add_argument("--min-score", type=float, default=0.5)
    p.add_argument("--gesture", default="fist", choices=("fist", "any"),
                   help="fist: 주먹=따라가기/손바닥=정지 (기본), any: 손이 보이면 항상 따라가기")
    p.add_argument("--gesture-frames", type=int, default=3, help="제스처 전환에 필요한 연속 프레임 수")
    p.add_argument("--k1", type=float, help="M1 게인 직접 지정 [°/px]")
    p.add_argument("--k2", type=float, help="M2 게인 직접 지정 [°/px]")
    p.add_argument("--gain", type=float, default=1.0, help="게인 배율 (오버슈트면 ↓, 느리면 ↑)")
    p.add_argument("--alpha", type=float, default=0.6, help="위치 필터 (↑ 빠름/떨림, ↓ 부드러움/지연)")
    p.add_argument("--beta", type=float, default=0.12, help="속도 필터")
    p.add_argument("--lead", type=float, default=0.18, help="지연 보상 예측 시간 [s]")
    p.add_argument("--cam-latency", type=float, default=0.04, help="카메라 촬영→수신 지연 [s]")
    p.add_argument("--deadzone", type=float, default=6.0, help="중앙 데드존 [px]")
    p.add_argument("--lost-stop", type=float, default=0.2,
                   help="마지막 검출 후 이 시간[s] 동안 새 검출이 없으면 S 로 정지")
    p.add_argument("--jump-px", type=float, default=150.0,
                   help="한 프레임 만에 이보다 크게 튄 검출은 무시 (2번 연속까지) [px]")
    p.add_argument("--max-step", type=float, default=None,
                   help="명령 1번 최대 이동 [펌웨어 °] (기본: 화면 200px 에 해당하는 각도)")
    p.add_argument("--max-lead-px", type=float, default=60.0, help="예측으로 앞서 보내는 최대량 [px]")
    p.add_argument("--rate", type=float, default=50.0, help="제어 스레드 주기 [Hz]")
    p.add_argument("--msl", type=int, default=3500, help="ESP32 최대 속도 CFG:MSL [Hz] (펌웨어 기본 3000)")
    p.add_argument("--acc", type=int, default=250,
                   help="ESP32 가속도 CFG:ACC [Hz/ms ×10] (250 = 25.0, 실기 시험에서 탈조 없음. 예전 값 150)")
    p.add_argument("--cam-fps", type=int, default=30, help="카메라에 요청할 fps")
    p.add_argument("--exposure", type=int, default=None,
                   help="노출 고정 [100µs 단위, 130 = 13ms]. 0 = 카메라 자동 노출. "
                        "안 주면(--cam-gain 도 안 주면) 자동 밝기 조절")
    p.add_argument("--cam-gain", type=int, default=None,
                   help="gain 고정 (0~63, -1 = 그대로 둠). 둘 중 하나만 주면 다른 쪽은 130/30 고정")
    p.add_argument("--bright-target", type=float, default=120.0,
                   help="자동 밝기 목표 (손 영역/화면 평균, 0~255, ±20 안이면 안 바꿈)")
    p.add_argument("--ae-exp-max", type=int, default=130, help="자동 밝기 노출 최대 [100µs] (번짐 방지)")
    p.add_argument("--ae-gain-max", type=int, default=40, help="자동 밝기 gain 최대")
    p.add_argument("--preview-port", type=int, default=5001, help="미리보기 포트 (0=끄기)")
    p.add_argument("--hold", action="store_true", help="종료 시 모터 전류 유지 (기본: 해제)")
    return p


if __name__ == "__main__":
    sys.exit(run(build_parser().parse_args()))
