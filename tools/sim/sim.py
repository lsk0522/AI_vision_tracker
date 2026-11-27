"""
hand_tracker.py 검증용 시뮬레이터 (배포하지 않음).
 - FakeESP32: 펌웨어 v2.0.7 의 명령/속도 프로파일을 pty 위에서 흉내
 - 실제 motor_esp32.py / state.py 를 그대로 사용
 - FakeCamera: 지연·프레임레이트가 있는 카메라, 진짜 모터 위치 기준으로 손 위치를 렌더
 - 'new' = hand_tracker.run, 'old' = 기존 set_target(EMA 0.12, ±80 클램프) + T:x:y
"""
import argparse, json, math, os, sys, threading, time, tty
import numpy as np

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
sys.path.insert(0, BACKEND)

import serial  # pty 에서는 DTR/RTS ioctl 이 안 되므로 무시
serial.Serial._update_dtr_state = lambda self: None
serial.Serial._update_rts_state = lambda self: None


class FakeESP32:
    def __init__(self):
        self.master, slave = os.openpty()
        tty.setraw(slave)
        self.port = os.ttyname(slave)
        self.SPD1 = self.SPD2 = 44.44
        self.SPX, self.MSL, self.ACC = 3.5, 3000.0, 3.0
        self.m = [0.0, 0.0]; self.t = [0, 0]; self.v = [0.0, 0.0]
        self.lock = threading.Lock()
        self.wlock = threading.Lock()
        self.cmds = {"T": 0, "MOVE": 0}
        self.ver_sent = False
        for fn in (self._reader, self._stepper, self._status):
            threading.Thread(target=fn, daemon=True).start()

    def _w(self, s):
        with self.wlock:
            os.write(self.master, s.encode())

    def angle(self):
        with self.lock:
            return self.m[0] / self.SPD1, self.m[1] / self.SPD2

    def _set_target_angles(self, a1, a2):
        a2 = max(-45.0, min(45.0, a2))
        lim = 85.0 if -45.0 <= a2 <= -25.0 else 180.0
        a1 = max(-lim, min(lim, a1))
        self.t = [round(a1 * self.SPD1), round(a2 * self.SPD2)]

    def _cmd(self, c):
        u = c.upper()
        with self.lock:
            if u.startswith("T:"):
                self.cmds["T"] += 1
                px, py = (int(x) for x in c[2:].split(":"))
                a1 = (int(self.m[0]) + int((px - 320) * self.SPX)) / self.SPD1
                a2 = (int(self.m[1]) + int((py - 240) * self.SPX)) / self.SPD2
                self._set_target_angles(a1, a2)
            elif u.startswith("MOVE J XY "):
                self.cmds["MOVE"] += 1
                a, b = (float(x) for x in c[10:].split())
                self._set_target_angles(a, b)
                self._w(f"OK MOVE J XY {a:.2f} {b:.2f}\n")
            elif u == "S":
                self.t = [round(self.m[0]), round(self.m[1])]; self.v = [0.0, 0.0]
            elif u.startswith("CFG:"):
                k, val = c[4:].split(":")
                k = k.upper()
                if k == "MSL": self.MSL = float(int(val))
                elif k == "ACC": self.ACC = float(val) / 10
                elif k == "SPX": self.SPX = float(val) / 1000
                self._w(f"OK CFG:{k}:{val}\n")
            elif u in ("MODE:POS", "MODE:TRACK"):
                self._w(f"OK {u}\n")
            elif u in ("POS", "STATUS"):
                pass

    def _reader(self):
        buf = b""
        while True:
            buf += os.read(self.master, 1024)
            if not self.ver_sent:
                self._w("VER:2.0.7\nOK BOOT\n"); self.ver_sent = True
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                s = line.decode(errors="ignore").strip()
                if s:
                    self._cmd(s)

    def _stepper(self):
        last = time.monotonic()
        while True:
            time.sleep(0.001)
            now = time.monotonic(); dt = now - last; last = now
            with self.lock:
                for i in range(2):
                    rem = self.t[i] - self.m[i]
                    if abs(rem) < 0.5:
                        self.m[i] = float(self.t[i]); self.v[i] = 0.0; continue
                    wall = max(8.0, min(self.MSL, abs(rem) * 8.0))
                    ms = max(1, int(round(dt * 1000)))
                    for _ in range(ms):
                        diff = abs(wall - self.v[i]); acc = self.ACC
                        if diff > 500: acc *= 3
                        elif diff > 200: acc *= 2
                        elif self.v[i] < 100: acc *= 0.3
                        if self.v[i] < wall: self.v[i] = min(wall, self.v[i] + acc)
                        else: self.v[i] = max(wall, self.v[i] - acc)
                    if self.v[i] > 5:
                        step = min(self.v[i] * dt, abs(rem))
                        self.m[i] += step if rem > 0 else -step

    def _status(self):
        while True:
            time.sleep(0.03)
            with self.lock:
                p1 = int((int(self.m[0]) / self.SPD1) * 100); p2 = int((int(self.m[1]) / self.SPD2) * 100)
                s1, s2 = self.v
            self._w(f"POS:{p1}:{p2}:{s1:.1f}:{s2:.1f}\n")


class MetaFrame(np.ndarray):
    pass


class FakeCamera:
    """30fps, 촬영→전달 지연 cam_delay. 손(목표)의 절대 각도 traj(t) 를 진짜 모터 위치 기준 화면 좌표로."""
    def __init__(self, esp, traj, k_true, cam_delay=0.05, fps=30, texture=False, noise=1.5):
        self.esp, self.traj, self.k_true = esp, traj, k_true
        self.w, self.h = 640, 480
        self.cam_delay, self.period, self.noise = cam_delay, 1.0 / fps, noise
        self.cond = threading.Condition(); self.frame = None; self.t = 0.0; self.seq = 0
        self.log = []   # (t_capture, 진짜 오차 px x, y)
        self.t0 = time.monotonic()
        self.tex = None
        if texture:
            import cv2
            rng = np.random.default_rng(1)
            n = rng.random((1600, 2400)).astype(np.float32)
            n = cv2.GaussianBlur(n, (0, 0), 6)
            n = (255 * (n - n.min()) / (n.max() - n.min())).astype(np.uint8)
            self.tex = cv2.cvtColor(n, cv2.COLOR_GRAY2BGR)
        self.blank = np.zeros((480, 640, 3), np.uint8)
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        pending = []
        nxt = time.monotonic()
        while True:
            now = time.monotonic()
            if now >= nxt:
                nxt += self.period
                tc = now
                m1, m2 = self.esp.angle()
                a1, a2 = self.traj(tc - self.t0)
                ex = (a1 - m1) / self.k_true[0]; ey = (a2 - m2) / self.k_true[1]
                self.log.append((tc - self.t0, ex, ey))
                if self.tex is not None:
                    ox = int(round(880 + m1 / self.k_true[0])); oy = int(round(560 + m2 / self.k_true[1]))
                    img = self.tex[oy:oy + 480, ox:ox + 640].copy()
                else:
                    img = self.blank
                f = np.asarray(img).view(MetaFrame)
                f.meta = (ex, ey)
                pending.append((tc + self.cam_delay, tc, f))
            while pending and pending[0][0] <= now:
                _, tc, f = pending.pop(0)
                with self.cond:
                    self.frame, self.t, self.seq = f, tc, self.seq + 1
                    self.cond.notify_all()
            time.sleep(0.002)

    def wait_new(self, last_seq, timeout=1.0):
        end = time.monotonic() + timeout
        with self.cond:
            while self.seq <= last_seq:
                left = end - time.monotonic()
                if left <= 0: return None, 0.0, last_seq
                self.cond.wait(left)
            return self.frame, self.t, self.seq

    def release(self): pass


class FakeDetector:
    def __init__(self, det_time=0.04, noise=1.5, pose_fn=None):
        self.det_time, self.noise = det_time, noise
        self.pose_fn = pose_fn or (lambda t: "FIST")
        self.t0 = time.monotonic()
        self.rng = np.random.default_rng(0)
    def detect(self, frame):
        time.sleep(self.det_time)
        ex, ey = frame.meta
        if abs(ex) > 310 or abs(ey) > 230:
            return None   # 화면 밖
        return {"cx": 320 + ex + self.rng.normal(0, self.noise), "cy": 240 + ey + self.rng.normal(0, self.noise),
                "w": 640, "h": 480, "score": 0.9, "pts": [],
                "pose": self.pose_fn(time.monotonic() - self.t0)}
    def close(self): pass


def make_traj(kind):
    if kind == "step":
        return lambda t: (0.0, 0.0) if t < 2.0 else ((10.0, -3.0) if t < 6.0 else (-6.0, 2.0))
    if kind == "sine":
        return lambda t: (8 * math.sin(2 * math.pi * 0.3 * t), 3 * math.sin(2 * math.pi * 0.2 * t))
    if kind == "fast":
        return lambda t: (12 * math.sin(2 * math.pi * 0.6 * t), 4 * math.sin(2 * math.pi * 0.45 * t))
    if kind == "gesture":
        return lambda t: (6 * math.sin(2 * math.pi * 0.25 * t), 2 * math.sin(2 * math.pi * 0.2 * t))
    if kind == "static":
        return lambda t: (0.0, 0.0)
    raise ValueError(kind)


def metrics(log, t_from):
    e = np.array([(x, y) for t, x, y in log if t >= t_from])
    rms = float(np.sqrt(np.mean(np.sum(e ** 2, axis=1))))
    p95 = float(np.percentile(np.hypot(e[:, 0], e[:, 1]), 95))
    return rms, p95


def step_metrics(log, t_step, target_px):
    """t_step 이후: 오버슈트(%), 정착시간(오차 < 15px 유지)"""
    seg = [(t, x) for t, x, y in log if t_step <= t < t_step + 4.0]
    if not seg: return None
    xs = np.array([x for _, x in seg]); ts = np.array([t for t, _ in seg])
    # target_px 는 스텝 직후 화면 오차 (양수). 오버슈트 = 반대 부호로 넘어간 최대치
    sgn = np.sign(xs[0]) if xs[0] != 0 else 1
    over = max(0.0, float(np.max(-sgn * xs)))
    settle = None
    for i in range(len(xs)):
        if np.all(np.abs(xs[i:]) < 15):
            settle = float(ts[i] - t_step); break
    return over, settle


def run_old(esp, cam, det, dur):
    """기존 detector_routes.set_target 로직 그대로 + motor_esp32 track 모드."""
    import state, motor_esp32
    motor_esp32.start(esp.port)
    time.sleep(2.5)
    state.control_mode = "auto"
    smooth = None; last_time = 0.0
    seq = 0; t_end = time.monotonic() + dur
    while time.monotonic() < t_end:
        frame, tf, seq = cam.wait_new(seq, 1.0)
        if frame is None: continue
        d = det.detect(frame)
        now = time.time()
        if d is None:
            if last_time and now - last_time > 1.0:
                state.point[0], state.point[1] = 320, 240
            continue
        tx, ty = int(d["cx"]), int(d["cy"])
        gap = (now - last_time) > 1.0
        if gap or smooth is None:
            smooth = [320.0, 240.0]; state.point[0], state.point[1] = 320, 240
        smooth[0] += 0.12 * (tx - smooth[0]); smooth[1] += 0.12 * (ty - smooth[1])
        ex = max(-80.0, min(80.0, smooth[0] - 320)); ey = max(-80.0, min(80.0, smooth[1] - 240))
        state.point[0] = 320 + int(ex); state.point[1] = 240 + int(ey)
        last_time = now


# ── 자동 밝기 시뮬레이션 (algo "bright") ───────────────────────────
# 가정한 모델 (실제 카메라 응답은 다를 수 있음):
#   픽셀 = 반사율 × 장면밝기 L × (노출/100) × (1 + gain/32), 0~255 로 잘림. 바꾼 값은 2프레임 뒤 반영.
#   배경 반사율 0.7, 손 1.0, 창문(오른쪽 200px) 4.0.
LIGHT_PHASES = [  # (시작 s, 이름, 장면밝기 L, 창문)
    (0, "보통", 48, False), (8, "아주 밝음(×3)", 144, False), (16, "조금 어두움(×0.8)", 38, False),
    (24, "아주 어두움(×0.4)", 19, False), (32, "보통+창문", 48, True)]
HAND_GAPS = [(11.0, 13.5), (21.0, 21.5), (34.0, 34.6), (37.0, 40.0)]   # 손이 안 보이는 구간 (s), --dur 40


def light_at(t):
    cur = LIGHT_PHASES[0]
    for ph in LIGHT_PHASES:
        if t >= ph[0]:
            cur = ph
    return cur


class LightCamera:
    """조명이 바뀌는 가짜 카메라. has_ctrl/set_ctrl 을 지원해서 AutoBright 가 조절할 수 있음."""
    HW, HH = 55, 65   # 손바닥 영역 반폭/반높이 (px)

    def __init__(self, exp0=130, gain0=30, fps=30, exp_ctrl=True):
        self.w, self.h = 640, 480
        self.period = 1.0 / fps
        self.exp, self.gain = exp0, gain0
        self.exp_ctrl = exp_ctrl
        self.pending = []           # (적용 프레임 seq, 이름, 값)
        self.sets = []              # (t, 이름, 값)
        self.released = False
        self.sets_after_release = 0
        self.log = []               # (t, 노출, gain, 손평균, 화면평균, 화면날아간비율, 손보임)
        self.cond = threading.Condition(); self.frame = None; self.t = 0.0; self.seq = 0
        self.t0 = time.monotonic()
        threading.Thread(target=self._loop, daemon=True).start()

    def has_ctrl(self, name):
        return self.exp_ctrl and name in ("exposure_time_absolute", "gain")

    def set_ctrl(self, name, val):
        if self.released:
            self.sets_after_release += 1
        self.sets.append((time.monotonic() - self.t0, name, int(val)))
        self.pending.append((self.seq + 2, name, int(val)))
        return True

    def hand_pos(self, t):
        return 320 + 150 * math.sin(2 * math.pi * 0.15 * t), 240 + 60 * math.sin(2 * math.pi * 0.11 * t)

    def _render(self, t):
        _, _, L, window = light_at(t)
        k = L * (self.exp / 100.0) * (1 + self.gain / 32.0)
        img = np.full((480, 640), 0.7 * k, np.float32)
        if window:
            img[:, 440:] = 4.0 * k
        vis = not any(a <= t < b for a, b in HAND_GAPS)
        hx, hy = self.hand_pos(t)
        if vis:
            x0, x1 = int(hx - self.HW), int(hx + self.HW)
            y0, y1 = int(hy - self.HH), int(hy + self.HH)
            img[max(0, y0):y1, max(0, x0):x1] = 1.0 * k
        g = np.clip(img, 0, 255).astype(np.uint8)
        hm = float(np.clip(k, 0, 255)) if vis else None
        self.log.append((t, self.exp, self.gain, hm, float(g.mean()),
                         float(np.count_nonzero(g >= 250)) / g.size, vis))
        f = np.dstack([g, g, g]).view(MetaFrame)
        f.meta = (hx, hy, vis)
        return f

    def _loop(self):
        nxt = time.monotonic()
        while True:
            now = time.monotonic()
            if now >= nxt:
                nxt += self.period
                for item in [x for x in self.pending if x[0] <= self.seq]:
                    self.pending.remove(item)
                    if item[1] == "gain": self.gain = item[2]
                    else: self.exp = item[2]
                f = self._render(now - self.t0)
                with self.cond:
                    self.frame, self.t, self.seq = f, now, self.seq + 1
                    self.cond.notify_all()
            time.sleep(0.002)

    def wait_new(self, last_seq, timeout=1.0):
        end = time.monotonic() + timeout
        with self.cond:
            while self.seq <= last_seq:
                left = end - time.monotonic()
                if left <= 0: return None, 0.0, last_seq
                self.cond.wait(left)
            return self.frame, self.t, self.seq

    def release(self):
        self.released = True


class LightDetector:
    """손이 보이면 손바닥 영역 꼭짓점을 랜드마크로 돌려줌 (PALM 0,5,9,13,17 가 영역을 감싸게)."""
    def detect(self, frame):
        time.sleep(0.03)
        hx, hy, vis = frame.meta
        if not vis:
            return None
        hw, hh = LightCamera.HW - 5, LightCamera.HH - 5
        corners = [(int(hx - hw), int(hy - hh)), (int(hx + hw), int(hy - hh)),
                   (int(hx + hw), int(hy + hh)), (int(hx - hw), int(hy + hh))]
        pts = [(int(hx), int(hy))] * 21
        for i, c in zip((0, 5, 9, 13, 17), corners + corners[:1]):
            pts[i] = c
        return {"cx": hx, "cy": hy, "w": 640, "h": 480, "score": 0.9, "pts": pts, "pose": "FIST"}
    def close(self): pass


def run_bright(a):
    import hand_tracker as ht
    args = ht.build_parser().parse_args(["--no-motor", "--gesture", "any", "--preview-port", "0"] + a.extra.split())
    exp0, gain0 = ht.camera_start_values(args)
    cam = LightCamera(exp0 if exp0 > 0 else 130, gain0 if gain0 >= 0 else 30)
    import io, contextlib
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ht.run(args, cam=cam, detector=LightDetector(), duration=a.dur)
    txt = out.getvalue()
    for l in txt.splitlines():
        if l.startswith("[camera]"):
            print(l)
    last = [l for l in txt.replace("\r", "\n").splitlines() if l.startswith(("TRACK", "LOST"))]
    if last:
        print("상태줄 예:", last[-1].strip())
    L = cam.log
    print(f"\n{'구간':<18}{'노출':>12}{'gain':>10}{'손 밝기(끝 1s)':>16}{'화면날아감':>10}{'변경':>6}")
    bounds = [ph[0] for ph in LIGHT_PHASES] + [a.dur]
    for i, ph in enumerate(LIGHT_PHASES):
        t1, t2 = bounds[i], bounds[i + 1]
        seg = [r for r in L if t1 <= r[0] < t2]
        if not seg: continue
        end = [r for r in seg if r[0] >= t2 - 1.0]
        hm = [r[3] for r in end if r[3] is not None]
        ch = sum(1 for s_ in cam.sets if t1 <= s_[0] < t2)
        print(f"{ph[1]:<18}{seg[0][1]:>5}→{seg[-1][1]:<5}{seg[0][2]:>4}→{seg[-1][2]:<4}"
              f"{(f'{np.mean(hm):.0f}' if hm else '-'):>14}{np.mean([r[5] for r in end]):>11.1%}{ch:>6}")
    exps = [r[1] for r in L]; gains = [r[2] for r in L]
    flips = 0
    for name in ("exposure_time_absolute", "gain"):
        v = [x[2] for x in cam.sets if x[1] == name]
        d = [np.sign(v[i + 1] - v[i]) for i in range(len(v) - 1)]
        flips += sum(1 for i in range(len(d) - 1) if d[i] and d[i + 1] and d[i] != d[i + 1])
    in_gap = [s_ for s_ in cam.sets if any(a_ + 0.1 <= s_[0] < min(b_, a_ + 2.0) for a_, b_ in HAND_GAPS)]
    print(json.dumps({"노출 범위": [min(exps), max(exps)], "gain 범위": [min(gains), max(gains)],
                      "변경 총": len(cam.sets), "방향 뒤집힘": flips,
                      "손 놓친 뒤 2초 안 변경": len(in_gap),
                      "종료 후 변경": cam.sets_after_release}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("algo", choices=("old", "new", "calib", "bright"))
    ap.add_argument("--traj", default="step")
    ap.add_argument("--ratio", type=float, default=1.0, help="진짜 °/px = 펌웨어 환산 × ratio")
    ap.add_argument("--dur", type=float, default=10.0)
    ap.add_argument("--use-calib", action="store_true")
    ap.add_argument("--extra", default="")
    a = ap.parse_args()
    if a.algo == "bright":
        return run_bright(a)

    k_fw = 3.5 / 44.44
    k_true = (k_fw * a.ratio, k_fw * a.ratio)
    esp = FakeESP32()
    base = make_traj(a.traj)
    traj = lambda t: tuple(v * a.ratio for v in base(t))  # 화면상 움직임은 동일하게
    cam = FakeCamera(esp, traj, k_true, texture=(a.algo == "calib"))
    det = FakeDetector()
    if a.traj == "gesture":
        det = FakeDetector(pose_fn=lambda t: "OPEN" if t < 2.0 else ("FIST" if t < 7.0 else "OPEN"))
        traj = lambda t: (6 * math.sin(2 * math.pi * 0.25 * t), 2 * math.sin(2 * math.pi * 0.2 * t))
        cam.traj = traj
        poslog = []
        def rec():
            t0 = time.monotonic()
            while True:
                poslog.append((time.monotonic() - t0, *esp.angle(), esp.v[0], esp.v[1])); time.sleep(0.01)
        threading.Thread(target=rec, daemon=True).start()

    import hand_tracker as ht
    ht.CALIB_PATH = "/tmp/sim_calib.json"
    if a.algo == "old":
        run_old(esp, cam, det, a.dur)
    else:
        args = ht.build_parser().parse_args(
            (["--calibrate"] if a.algo == "calib" else []) + ["--preview-port", "0"] + a.extra.split())
        if a.algo == "new" and not a.use_calib and os.path.exists(ht.CALIB_PATH):
            os.remove(ht.CALIB_PATH)
        motor = ht.Motor(esp.port)
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ht.run(args, cam=cam, detector=det, motor=motor, duration=a.dur)
        txt = out.getvalue()
        if a.algo == "calib":
            print("\n".join(l for l in txt.splitlines() if l.startswith("[calib]")))
            return
    res = {"algo": a.algo, "traj": a.traj, "ratio": a.ratio, "cmds": dict(esp.cmds)}
    if a.traj == "gesture":
        P = np.array(poslog)
        def moved(t1, t2):
            seg = P[(P[:, 0] >= t1) & (P[:, 0] <= t2)]
            return float(np.max(np.abs(seg[:, 1:3] - seg[0, 1:3]))) if len(seg) else None
        # 감지 지연 보정: 카메라 t0 기준으로 정렬
        res["손바닥 구간(0.5~2.0s) 이동량°"] = moved(0.5, 2.0)
        res["주먹 구간(3~7s) 추적 오차 rms px"] = metrics([l for l in cam.log if 3.5 <= l[0] <= 7.0], 0)[0]
        after = P[P[:, 0] >= 7.0]
        stop_t = next((r[0] for r in after if abs(r[3]) < 1 and abs(r[4]) < 1), None)
        res["손바닥 후 완전 정지까지 s"] = None if stop_t is None else round(stop_t - 7.0, 3)
        res["정지 후(7.5s~) 이동량°"] = moved(7.5, a.dur)
        print(json.dumps(res, ensure_ascii=False)); return
    if a.traj == "step":
        k = k_true[0]
        res["step1"] = step_metrics(cam.log, 2.0, 0)
        res["step2"] = step_metrics(cam.log, 6.0, 0)
    else:
        res["rms_px"], res["p95_px"] = metrics(cam.log, 3.0)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
