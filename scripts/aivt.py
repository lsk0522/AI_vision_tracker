#!/usr/bin/env python3
"""
aivt — AI Vision Tracker 관리 도구 (Mac 에서 실행)

  aivt                 메뉴 (번호로 선택)
  aivt status          파이 연결/코드 버전/실행 상태
  aivt sync            Mac → 파이 코드 업데이트 (바뀐 파일만, 백업 후)
  aivt run [옵션]      자동 업데이트 → 손 추적 실행   (예: aivt run --gain 0.8)
  aivt calibrate       자동 업데이트 → 카메라-모터 캘리브레이션
  aivt dashboard       자동 업데이트 → 기존 웹 대시보드(main.py) 실행
  aivt stop            파이에서 실행 중인 프로그램 정지
  aivt preview | web   손 추적 미리보기(5001) / 웹 대시보드(5000) 브라우저로 열기
  aivt watch           Mac 에서 파일을 저장할 때마다 자동 업데이트
  aivt diff 파일       Mac ↔ 파이 파일 비교 (예: aivt diff backend/state.py)
  aivt rollback        마지막 업데이트 되돌리기
  aivt deps            파이 가상환경 + 패키지 설치 (mediapipe 등)
  aivt clean           파이 저장공간 분석·정리 (코드/자료는 Mac 으로 백업 후 삭제)
  aivt ssh             파이 터미널 접속
  aivt setpath         파이 코드 위치 다시 선택
  aivt install         'aivt' 명령 + 더블클릭 실행 파일(AIVT.command) 설치

기준은 이 Mac 폴더입니다. 파이에서 직접 고친 파일은 덮어쓰기 전에 물어봅니다.
덮어쓴 파일은 파이의 ~/.aivt/backups 에 남습니다 (최근 10번).
"""
import difflib
import getpass
import hashlib
import io
import json
import os
import shlex
import socket
import subprocess
import sys
import tarfile
import time

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
REMOTE_SRC = os.path.join(SCRIPTS, "aivt_remote.py")
CONF_PATH = os.path.expanduser(os.environ.get("AIVT_CONF", "~/.config/ai_vision_tracker/aivt.json"))
HOST = os.environ.get("AIVT_HOST", "pi")
REMOTE = "~/.aivt/remote.py"

sys.path.insert(0, SCRIPTS)
import aivt_remote as R   # 같은 제외 규칙/해시 함수 사용 (Mac 과 파이가 같은 기준)

C = {"g": "\033[32m", "y": "\033[33m", "r": "\033[31m", "b": "\033[1m", "d": "\033[2m", "0": "\033[0m"}
if not sys.stdout.isatty():
    C = {k: "" for k in C}


def say(msg, c=None):
    print(f"{C[c]}{msg}{C['0']}" if c else msg, flush=True)


def ask(q, default="n"):
    if not sys.stdin.isatty():
        return default
    try:
        a = input(q).strip().lower()
    except EOFError:
        return default
    return a or default


# ──────────────────────────── 설정 ────────────────────────────
def load_conf():
    try:
        with open(CONF_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_conf(c):
    os.makedirs(os.path.dirname(CONF_PATH), exist_ok=True)
    with open(CONF_PATH, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)


# ──────────────────────────── ssh ────────────────────────────
def ssh_base(tty=False):
    cp = os.path.expanduser("~/.ssh/aivt-%C")
    b = ["ssh", "-o", "ControlMaster=auto", "-o", f"ControlPath={cp}", "-o", "ControlPersist=120",
         "-o", "ConnectTimeout=10"]
    if tty:
        b.append("-t")
    return b + [HOST]


_remote_ready = False


def ensure_remote():
    """파이에 도우미(remote.py) 설치/갱신."""
    global _remote_ready
    if _remote_ready:
        return
    with open(REMOTE_SRC, "rb") as f:
        src = f.read()
    cmd = ("mkdir -p ~/.aivt && cat > ~/.aivt/remote.py.new && "
           "mv ~/.aivt/remote.py.new ~/.aivt/remote.py && echo ok")
    r = subprocess.run(ssh_base() + [cmd], input=src, capture_output=True)
    if r.returncode != 0 or b"ok" not in r.stdout:
        err = r.stderr.decode(errors="ignore").strip()
        say(f"❌ 파이에 연결하지 못했습니다 ({HOST}). {err[-300:]}", "r")
        say("   파이 전원/네트워크 확인 →  ssh pi  로 접속되는지 먼저 확인하세요.", "d")
        sys.exit(2)
    _remote_ready = True


def remote(*args, stdin=None):
    ensure_remote()
    cmd = "python3 " + REMOTE + " " + " ".join(shlex.quote(a) for a in args)
    if stdin is None:   # 터미널 입력을 ssh 가 먹지 않도록
        r = subprocess.run(ssh_base() + [cmd], stdin=subprocess.DEVNULL, capture_output=True)
    else:
        r = subprocess.run(ssh_base() + [cmd], input=stdin, capture_output=True)
    if r.returncode != 0:
        say(f"❌ 파이 명령 실패: {args[0]}\n{r.stderr.decode(errors='ignore')[-800:]}", "r")
        sys.exit(3)
    out = r.stdout.decode(errors="ignore").strip()
    try:
        return json.loads(out.splitlines()[-1]) if out else {}
    except ValueError:
        return {"raw": out}


def interactive(remote_cmd):
    """ssh -t 로 파이에서 직접 실행 (Ctrl+C 가 파이 프로그램에 전달됨)."""
    ensure_remote()
    return subprocess.call(ssh_base(tty=True) + [remote_cmd])


def pi_ip():
    try:
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "find_pi.py")],
                             stdin=subprocess.DEVNULL, capture_output=True, text=True,
                             timeout=30).stdout.strip()
        return out or None
    except (OSError, subprocess.SubprocessError):
        return None


# ──────────────────────────── 파이 코드 위치 ────────────────────────────
def choose_root(force=False):
    conf = load_conf()
    if conf.get("pi_root") and not force:
        return conf["pi_root"]
    say("🔎 파이에서 코드 위치를 찾는 중...", "d")
    info = remote("locate")
    cands = info.get("candidates", [])
    home = info.get("home", "~")
    layout_ok = [c for c in cands if c.get("root")]
    others = [c for c in cands if not c.get("root")]
    order = sorted(layout_ok, key=lambda c: (c["kind"] != "running", not c["git"], -c["mtime"]))
    options = [c["root"] for c in order]
    default_new = f"{home}/AI_vision_tracker"
    if default_new not in options:
        options.append(default_new)

    say("\n파이의 코드 위치를 선택하세요 (이 폴더 아래 backend/ scripts/ firmware/ 를 Mac 과 맞춥니다):", "b")
    for i, o in enumerate(options, 1):
        tag = ""
        c = next((c for c in order if c["root"] == o), None)
        if c:
            tag = "  ← 지금 main.py 실행 중" if c["kind"] == "running" else ""
            tag += "  (git)" if c["git"] else ""
        else:
            tag = "  (새로 만들기)"
        say(f"  {i}) {o}{tag}")
    if others:
        say("  참고: 다른 구조의 코드도 있습니다 (동기화 대상 아님):", "d")
        for c in others:
            say(f"      {c['code_dir']}", "d")
    a = ask(f"번호 [1]: ", "1")
    try:
        root = options[int(a) - 1]
    except (ValueError, IndexError):
        root = a if a.startswith("/") else options[0]
    conf["pi_root"] = root
    save_conf(conf)
    say(f"✔ 파이 코드 위치: {root}", "g")
    return root


# ──────────────────────────── 동기화 ────────────────────────────
def version_of(man):
    h = hashlib.sha256(json.dumps(sorted(man.items())).encode()).hexdigest()
    return h[:8]


def plan(root):
    mac = R.manifest(ROOT)
    pi = remote("manifest", root)
    P, S = pi.get("files", {}), pi.get("synced", {})
    send = sorted(f for f in mac if P.get(f) != mac[f])
    # 파이에 있는 파일인데, 마지막으로 보낸 내용과 다르면 → 파이에서 직접 고쳤거나 처음 맞추는 파일
    conflicts = [f for f in send if f in P and S.get(f) != P[f]]
    pi_only = sorted(f for f in P if f not in mac)
    return {"mac": mac, "pi": P, "synced": S, "send": send, "conflicts": conflicts,
            "pi_only": pi_only, "running": pi.get("running", {}), "venv": pi.get("venv"),
            "mac_v": version_of(mac), "pi_v": version_of({f: P[f] for f in mac if f in P})}


def show_diff(root, rel, limit=80):
    r = subprocess.run(ssh_base() + ["cat " + shlex.quote(f"{root}/{rel}")],
                       stdin=subprocess.DEVNULL, capture_output=True)
    pi_txt = r.stdout.decode(errors="replace").splitlines()
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as f:
            mac_txt = f.read().splitlines()
    except OSError:
        mac_txt = []
    d = list(difflib.unified_diff(pi_txt, mac_txt, f"파이:{rel}", f"Mac:{rel}", lineterm="", n=2))
    if not d:
        say(f"  (내용 차이 없음 또는 바이너리) {rel}", "d")
        return
    for line in d[:limit]:
        c = "g" if line.startswith("+") and not line.startswith("+++") else \
            "r" if line.startswith("-") and not line.startswith("---") else None
        say(line, c)
    if len(d) > limit:
        say(f"  ... ({len(d) - limit}줄 더)", "d")


def sync(yes=False, dry=False, quiet=False):
    root = choose_root()
    p = plan(root)
    send, conflicts = p["send"], p["conflicts"]
    if not send:
        # 처음 맞춘 상태 기록 (이미 같은 파일들)
        if any(p["synced"].get(f) != h for f, h in p["mac"].items() if p["pi"].get(f) == h) and not dry:
            _apply(root, p, [])
        if not quiet:
            say(f"✅ 파이 코드 최신  (v{p['mac_v']})", "g")
        return True

    say(f"⬆ 업데이트 필요: {len(send)}개 파일  (파이 v{p['pi_v']} → Mac v{p['mac_v']})", "y")
    for f in send[:20]:
        mark = "⚠ 파이에서 변경됨" if f in conflicts else ("새 파일" if f not in p["pi"] else "")
        say(f"   {f}  {C['y'] + mark + C['0'] if mark else ''}")
    if len(send) > 20:
        say(f"   ... 외 {len(send) - 20}개", "d")
    if dry:
        return False

    if conflicts and not yes:
        say(f"\n⚠ 위 파일 중 {len(conflicts)}개는 파이 쪽 내용이 마지막 동기화와 다릅니다", "y")
        say("  (처음 맞추는 경우이거나, 파이에서 직접 수정한 경우). 덮어쓴 원본은 백업됩니다.", "d")
        while True:
            a = ask("  y=모두 Mac 버전으로 / s=그 파일들만 건너뛰기 / d=차이 보기 / n=취소 [n]: ", "n")
            if a == "d":
                for f in conflicts:
                    show_diff(root, f)
                continue
            break
        if a == "n":
            say("취소했습니다.", "d")
            return False
        if a == "s":
            send = [f for f in send if f not in conflicts]
            if not send:
                say("보낼 파일이 없습니다.", "d")
                return False
    res = _apply(root, p, send)
    say(f"✅ 업데이트 완료: {res.get('written', 0)}개 파일 (새 파일 {res.get('added', 0)})  "
        f"→ 파이 v{p['mac_v'] if len(send) == len(p['send']) else '부분'}", "g")
    say(f"   백업: {res.get('backup')}   (되돌리기: aivt rollback)", "d")
    run_ = p["running"]
    if run_.get("main") or run_.get("hand"):
        say("   ⚠ 실행 중인 프로그램은 다시 시작해야 새 코드가 적용됩니다.", "y")
    return True


def _apply(root, p, send):
    buf = io.BytesIO()
    synced = {f: h for f, h in p["mac"].items() if p["pi"].get(f) == h}
    synced.update({f: p["mac"][f] for f in send})
    meta = json.dumps({"sent": synced, "version": p["mac_v"],
                       "from": f"{getpass.getuser()}@{socket.gethostname()}"}).encode()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        ti = tarfile.TarInfo(".aivt_meta.json")
        ti.size, ti.mtime = len(meta), int(time.time())
        tf.addfile(ti, io.BytesIO(meta))
        for f in send:
            full = os.path.join(ROOT, f)
            ti = tf.gettarinfo(full, arcname=f)
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            with open(full, "rb") as fh:
                tf.addfile(ti, fh)
    return remote("apply", root, stdin=buf.getvalue())


# ──────────────────────────── 명령들 ────────────────────────────
def cmd_status():
    ip = pi_ip()
    say(f"파이: {HOST}  {ip or '(IP 못 찾음)'}", "b")
    root = choose_root()
    p = plan(root)
    ok = not p["send"]
    say(f"코드 위치: {root}")
    say(f"Mac  버전: v{p['mac_v']}   ({len(p['mac'])}개 파일)")
    say(f"파이 버전: v{p['pi_v']}   " + ("✅ 최신" if ok else f"⬆ {len(p['send'])}개 다름"),
        "g" if ok else "y")
    if p["conflicts"]:
        say(f"  ⚠ 파이에서 바뀐 파일 {len(p['conflicts'])}개: " + ", ".join(p["conflicts"][:5]), "y")
    if p["pi_only"]:
        say(f"  파이에만 있는 파일 {len(p['pi_only'])}개 (삭제하지 않음): " + ", ".join(p["pi_only"][:5]), "d")
    info = remote("locate")
    ls = info.get("last_sync", {})
    if ls.get("time"):
        say(f"마지막 업데이트: {ls['time']}  (from {ls.get('from')})", "d")
    run_ = p["running"]
    say("실행 중: " + (", ".join(
        [f"main.py(pid {x})" for x in run_.get("main", [])] +
        [f"hand_tracker.py(pid {x})" for x in run_.get("hand", [])]) or "없음"))
    venv = p.get("venv") or "python3"
    r = subprocess.run(ssh_base() + [f"{shlex.quote(venv)} -c 'import mediapipe as m; print(m.__version__)'"],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    mp = r.stdout.strip() or "없음 (aivt deps 로 설치)"
    say(f"파이 Python: {venv}   mediapipe: {mp}", "d")


def cmd_launch(what, args, do_sync=True):
    if do_sync and not sync(quiet=False):
        if ask("업데이트 없이 그대로 실행할까요? [y/N]: ", "n") != "y":
            return 1
    root = choose_root()
    ip = pi_ip()
    if what == "hand" and ip and "--calibrate" not in args:
        say(f"👀 미리보기: http://{ip}:5001/   (다른 창에서 aivt preview)", "d")
    if what == "main" and ip:
        say(f"🌐 웹 대시보드: http://{ip}:5000/   (aivt web)", "d")
    say("■ 종료: Ctrl+C", "d")
    cmd = "python3 " + REMOTE + " launch " + " ".join(shlex.quote(x) for x in [root, what] + list(args))
    return interactive(cmd)


def cmd_open(port):
    ip = pi_ip()
    if not ip:
        say("❌ 파이를 찾지 못했습니다", "r")
        return 1
    url = f"http://{ip}:{port}/"
    say(url)
    if sys.platform == "darwin":
        subprocess.call(["open", url])
    return 0


def cmd_rollback():
    root = choose_root()
    if ask("마지막 업데이트를 되돌릴까요? (파이 파일을 업데이트 이전으로) [y/N]: ", "n") != "y":
        return 1
    r = remote("rollback", root)
    if r.get("ok"):
        say(f"↩ 되돌림: 복원 {r['restored']}개, 새로 생겼던 파일 삭제 {r['removed']}개", "g")
        return 0
    say(f"❌ {r.get('error')}", "r")
    return 1


def cmd_watch(interval=2.0):
    say("👁 Mac 파일 변경을 감시합니다. 저장하면 자동으로 파이에 올립니다. (종료: Ctrl+C)", "b")
    last = None
    try:
        while True:
            v = version_of(R.manifest(ROOT))
            if v != last:
                if last is not None:
                    say(time.strftime("[%H:%M:%S] ") + "변경 감지", "d")
                sync()
                last = v
            time.sleep(interval)
    except KeyboardInterrupt:
        say("\n감시 종료", "d")


DEPS = ["mediapipe", "pyserial"]
# mediapipe 1.x / 0.10.20+ 의 aarch64 휠은 CPU 의 AES 명령이 필요 → Raspberry Pi 4 (Cortex-A72, AES 없음) 에서
# "FATAL ERROR: This binary was compiled with aes enabled" 로 죽음. 그런 CPU 에선 마지막으로 되는 0.10.18 고정.
MP_NO_AES = "mediapipe==0.10.18"
# import 만으로는 위 오류가 안 나고 모델을 만들 때 죽으므로, 실제로 손 모델을 로드해서 확인
CHECK = ("{ .venv/bin/python -c 'import mediapipe as m, cv2, numpy, serial; "
         "from mediapipe.tasks.python import vision, BaseOptions; "
         "vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions("
         "base_options=BaseOptions(model_asset_path=\"hand_landmarker.task\"))); "
         "print(\"✅ mediapipe\", m.__version__, \"/ opencv\", cv2.__version__, \"(손 모델 로드 OK)\")' 2>&1 | grep -v -E \"^(W|I)0000|inference_feedback|XNNPACK\"; "
         "test ${PIPESTATUS[0]} -eq 0; }")


def pi_deps():
    """파이 CPU 에 맞는 설치 목록."""
    r = subprocess.run(ssh_base() + ["grep -m1 -w -c aes /proc/cpuinfo"], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True)
    if r.stdout.strip() == "0":
        say(f":: 이 파이 CPU 에는 AES 명령이 없음 (Pi 4 등) → {MP_NO_AES} 사용", "d")
        return [MP_NO_AES] + DEPS[1:]
    return DEPS


def cmd_deps():
    """손 추적 전용 가상환경(backend/.venv)에 필요한 것만 설치. 기존 main.py 의 .venv 는 건드리지 않음.
    1) 파이에서 직접 설치 (끊겨도 이어받기 재시도)  2) 실패하면 Mac 에서 받아서 파이로 보내 설치"""
    root = choose_root()
    sync()
    deps = " ".join(shlex.quote(d) for d in pi_deps())
    code = shlex.quote(root + "/backend")
    script = f"""
ARCH=$(uname -m); BITS=$(getconf LONG_BIT)
echo ":: 파이: $ARCH / ${{BITS}}bit / $(python3 --version 2>&1)"
if [ "$ARCH" != "aarch64" ] || [ "$BITS" != "64" ]; then
  echo "❌ mediapipe 는 64비트 OS(aarch64)에서만 설치됩니다. 지금 OS: $ARCH/${{BITS}}bit"
  exit 3
fi
cd {code} || exit 3
FREE=$(df -Pm . | awk 'NR==2{{print $4}}')
echo ":: 남은 공간: ${{FREE}}MB"
if [ "$FREE" -lt 1200 ]; then
  echo "❌ 공간이 부족합니다 (최소 1200MB 필요). 정리 후 다시 실행하세요:"
  echo "   ssh pi 'rm -rf ~/.aivt/wheels ~/.cache/pip'   /   ssh -t pi 'sudo apt clean'"
  echo "   큰 폴더 확인: ssh pi 'du -sh ~/* ~/.cache 2>/dev/null | sort -h | tail'"
  exit 3
fi
rm -rf ~/.aivt/wheels
if [ ! -x .venv/bin/python ]; then
  echo ":: 손 추적 전용 가상환경 생성: $(pwd)/.venv  (기존 main.py 환경과 분리)"
  python3 -m venv .venv || exit 3
fi
.venv/bin/python -m pip install -q --no-cache-dir --upgrade pip
for i in 1 2 3; do
  echo ":: 설치 시도 $i/3: {deps} (몇 분 걸릴 수 있습니다)"
  if .venv/bin/python -m pip install --no-cache-dir --timeout 60 --retries 10 --resume-retries 30 {deps}; then
    {CHECK} && exit 0
    echo "❌ 설치는 됐지만 이 파이에서 mediapipe 가 실행되지 않습니다 (위 오류 참고)"
    exit 3
  fi
  sleep 3
done
exit 4
"""
    rc = interactive("bash -c " + shlex.quote(script))
    if rc == 0:
        say("✅ 설치 완료. 다음:  aivt calibrate  →  aivt run", "g")
        return 0
    if rc != 4:
        return rc
    say("\n파이 인터넷이 자꾸 끊겨서 실패했습니다.", "y")
    if ask("Mac 에서 패키지를 받아 파이로 보내 설치할까요? [Y/n]: ", "y") == "n":
        return 1
    return deps_via_mac(root)


def deps_via_mac(root):
    import shutil
    import tempfile
    r = subprocess.run(ssh_base() + ["python3 -c 'import sys; print(\"%d%d\" % sys.version_info[:2])'"],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    pyv = r.stdout.strip() or "311"
    deps = pi_deps()
    tmp = tempfile.mkdtemp(prefix="aivt_wheels_")
    say(f":: Mac 에서 다운로드 (파이용 aarch64 / Python {pyv[0]}.{pyv[1:]})...", "b")
    plats = []
    for p in ("manylinux_2_28_aarch64", "manylinux_2_27_aarch64", "manylinux_2_24_aarch64",
              "manylinux_2_17_aarch64", "manylinux2014_aarch64", "linux_aarch64"):
        plats += ["--platform", p]
    cmd = [sys.executable, "-m", "pip", "download", "-d", tmp, "--only-binary=:all:",
           "--python-version", pyv, "--implementation", "cp", "--abi", f"cp{pyv}", "--abi", "abi3",
           "--abi", "none", *plats, "--timeout", "60", "--retries", "10", *deps]
    if subprocess.call(cmd) != 0:
        say("❌ Mac 에서도 다운로드에 실패했습니다. (Mac 에 pip 가 없다면: python3 -m ensurepip --user)", "r")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    wheels = [f for f in os.listdir(tmp) if f.endswith(".whl")]
    size = sum(os.path.getsize(os.path.join(tmp, f)) for f in wheels) / 1e6
    say(f":: 파이로 전송: {len(wheels)}개, {size:.0f} MB", "b")
    rdir = "~/.aivt/wheels"
    r = subprocess.run(ssh_base() + ["rm -rf ~/.aivt/wheels; df -Pm ~ | awk 'NR==2{print $4}'"],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    try:
        free = int(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        free = -1
    need = int(size * 5) + 300      # 압축 해제·설치 공간까지 대략
    if 0 <= free < need:
        say(f"❌ 파이 공간 부족: 남은 {free}MB / 필요 약 {need}MB. 정리 후 다시 aivt deps", "r")
        say("   ssh pi 'rm -rf ~/.cache/pip'  /  ssh -t pi 'sudo apt clean'", "d")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for f in wheels:
            tf.add(os.path.join(tmp, f), arcname=f)
    r = subprocess.run(ssh_base() + [f"rm -rf {rdir} && mkdir -p {rdir} && tar -xf - -C {rdir} && echo ok"],
                       input=buf.getvalue(), capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
    if b"ok" not in r.stdout:
        say("❌ 전송 실패: " + r.stderr.decode(errors="ignore")[-300:], "r")
        return 1
    code = shlex.quote(root + "/backend")
    script = f"""
cd {code} && .venv/bin/python -m pip install --no-cache-dir --no-index --find-links {rdir} {' '.join(shlex.quote(d) for d in deps)} &&
{CHECK} &&
rm -rf {rdir}
"""
    rc = interactive("bash -c " + shlex.quote(script))
    subprocess.run(ssh_base() + [f"rm -rf {rdir}"], stdin=subprocess.DEVNULL, capture_output=True)
    if rc == 0:
        say("✅ 설치 완료. 다음:  aivt calibrate  →  aivt run", "g")
    return rc


def _mb(n):
    if n is None:
        return "?"
    return f"{n / 1e9:.1f}G" if n >= 1e9 else f"{n / 1e6:.0f}M"


CAT = {"cache": "캐시", "code": "코드/자료", "data": "데이터", "system": "패키지"}


def cmd_clean():
    """파이 저장공간 분석 → 고른 것만 정리. 코드/데이터는 Mac 으로 백업한 뒤 삭제."""
    root = choose_root()
    say("🔎 파이 저장공간 분석 중... (1~2분 걸릴 수 있습니다)", "d")
    sc = remote("scan", root)
    items = sorted(sc.get("items", []), key=lambda i: (list(CAT).index(i["cat"]), -i["size"]))
    say(f"\n💾 파이 디스크: 전체 {_mb(sc.get('total'))}, 남은 공간 {_mb(sc.get('free'))}", "b")
    tops = {k: v for k, v in (sc.get("tops") or {}).items() if v}
    if tops:
        say("   큰 영역: " + ", ".join(f"{k} {_mb(v)}" for k, v in sorted(tops.items(), key=lambda kv: -kv[1])), "d")
    if not items:
        say("정리할 후보가 없습니다.", "d")
        return 0
    say("\n  번호  종류       크기   항목", "b")
    for n, it in enumerate(items, 1):
        star = "★" if it["default"] else " "
        bk = " [Mac 백업 후 삭제]" if it["backup"] else ""
        say(f"  {star}{n:>3}  {CAT[it['cat']]:<8} {_mb(it['size']):>6}   {it['title']}{bk}")
        if it.get("note"):
            say(f"                          {it['note']}", "d")
    say("\n  ★ = 지워도 안전한 캐시", "d")
    a = ask("지울 번호를 띄어 쓰기로 (예: 1 2 7), a=★ 전부, q=취소: ", "q")
    if a in ("q", "n", ""):
        say("취소했습니다.", "d")
        return 1
    if a == "a":
        sel = [it for it in items if it["default"]]
    else:
        sel = []
        for tok in a.replace(",", " ").split():
            if tok.isdigit() and 1 <= int(tok) <= len(items):
                sel.append(items[int(tok) - 1])
    if not sel:
        return 1
    total = sum(it["size"] for it in sel)
    say(f"\n선택: {len(sel)}개, 약 {_mb(total)}", "b")
    for it in sel:
        say(f"  - {it['title']} ({_mb(it['size'])})" + ("  → Mac 으로 백업" if it["backup"] else ""))
    if ask("정말 지울까요? [y/N]: ", "n") != "y":
        say("취소했습니다.", "d")
        return 1

    if any(it["id"] == "flat" for it in sel) and remote("locate").get("running", {}).get("main"):
        say("⚠ 옛 main.py 가 실행 중입니다. 먼저 정지합니다.", "y")
        remote("stop")

    # 1) 백업 (Mac 홈의 AIVT_pi_backup — iCloud 동기화 폴더 아님)
    bdir = os.path.expanduser(f"~/AIVT_pi_backup/{time.strftime('%Y%m%d-%H%M%S')}")
    to_delete = []
    for it in sel:
        if it["sudo"]:
            continue
        if it["backup"]:
            os.makedirs(bdir, exist_ok=True)
            out = os.path.join(bdir, it["id"].replace(":", "_") + ".tgz")
            rel = [p.lstrip("/") for p in it["paths"]]
            say(f"⬇ 백업: {it['title']} → {out}", "d")
            with open(out, "wb") as f:
                rc = subprocess.call(ssh_base() + ["tar -C / --exclude=.venv --exclude=__pycache__ -czf - " + " ".join(shlex.quote(r) for r in rel)],
                                     stdin=subprocess.DEVNULL, stdout=f)
            try:
                with tarfile.open(out, "r:gz") as tf:
                    n = sum(1 for _ in tf)
            except (tarfile.TarError, OSError):
                n = 0
            if rc != 0 or n == 0:
                say(f"❌ 백업 실패 → 이 항목은 지우지 않습니다: {it['title']}", "r")
                continue
            say(f"   ✔ {n}개 항목, {_mb(os.path.getsize(out))}", "d")
        to_delete += it["paths"]

    # 2) 일반 삭제
    if to_delete:
        r = remote("delete", stdin=json.dumps(to_delete).encode())
        if r.get("skipped"):
            say("   건너뜀: " + ", ".join(r["skipped"][:5]), "y")

    # 3) 관리자 권한이 필요한 것 (비밀번호를 물을 수 있음)
    cmds = []
    if any(it["id"] == "apt" for it in sel):
        cmds.append("sudo apt-get clean")
    if any(it["id"] == "journal" for it in sel):
        cmds.append("sudo journalctl --vacuum-size=50M")
    pkgs = [p for it in sel if it["id"].startswith("pkg:") for p in it["paths"]]
    if pkgs:
        cmds.append("sudo apt-get purge -y " + " ".join(shlex.quote(p) for p in pkgs))
        cmds.append("sudo apt-get autoremove -y")
        cmds.append("sudo apt-get clean")
    if cmds:
        say("🔑 관리자 권한 작업 (파이 비밀번호를 물을 수 있어요): " + " ; ".join(cmds), "d")
        interactive(" && ".join(cmds))

    r = subprocess.run(ssh_base() + ["df -B1 --output=avail ~ | tail -1"], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True)
    try:
        free = int(r.stdout.strip())
    except ValueError:
        free = None
    say(f"\n✅ 정리 완료. 파이 남은 공간: {_mb(sc.get('free'))} → {_mb(free)}", "g")
    if os.path.isdir(bdir):
        say(f"   백업 위치: {bdir}", "d")
        say("   복원하려면: cat 백업파일.tgz | ssh pi 'tar -C / -xzf -'", "d")
    return 0


def cmd_ssh():
    root = choose_root()
    return interactive(f"cd {shlex.quote(root)}/backend 2>/dev/null || cd {shlex.quote(root)}; exec $SHELL -l")


def cmd_install():
    # 1) 실행 권한
    for f in os.listdir(SCRIPTS):
        if f.endswith((".sh", ".py")):
            p = os.path.join(SCRIPTS, f)
            os.chmod(p, os.stat(p).st_mode | 0o111)
    # 2) zsh/bash 별칭
    line = f'alias aivt="python3 {shlex.quote(os.path.join(SCRIPTS, "aivt.py"))}"'
    begin, end = "# >>> aivt >>>", "# <<< aivt <<<"
    for rc in ("~/.zshrc", "~/.bashrc"):
        rc = os.path.expanduser(rc)
        if rc.endswith(".bashrc") and not os.path.exists(rc):
            continue
        txt = open(rc, encoding="utf-8").read() if os.path.exists(rc) else ""
        if begin in txt:
            pre, rest = txt.split(begin, 1)
            txt = pre + rest.split(end, 1)[-1].lstrip("\n")
        txt = txt.rstrip("\n") + f"\n\n{begin}\n{line}\n{end}\n"
        with open(rc, "w", encoding="utf-8") as f:
            f.write(txt)
        say(f"✔ {rc} 에 aivt 명령 등록")
    # 3) 더블클릭 실행 파일
    cmdfile = os.path.join(ROOT, "AIVT.command")
    with open(cmdfile, "w", encoding="utf-8") as f:
        f.write(f'#!/bin/bash\ncd {shlex.quote(ROOT)}\nexec python3 scripts/aivt.py\n')
    os.chmod(cmdfile, 0o755)
    say(f"✔ 더블클릭 실행 파일: {cmdfile}")
    say("\n새 터미널을 열면  aivt  로 바로 쓸 수 있습니다. (지금 창: source ~/.zshrc)", "g")
    say("AIVT.command 를 Dock 이나 바탕화면으로 끌어다 두면 클릭 한 번으로 메뉴가 열립니다.", "d")


MENU = [
    ("손 추적 실행 (자동 업데이트)", lambda: cmd_launch("hand", [])),
    ("캘리브레이션", lambda: cmd_launch("hand", ["--calibrate"])),
    ("웹 대시보드(main.py) 실행", lambda: cmd_launch("main", [])),
    ("업데이트만 (Mac → 파이)", lambda: sync()),
    ("상태 보기", cmd_status),
    ("실행 중인 프로그램 정지", lambda: say(remote("stop").get("raw", ""))),
    ("손 추적 미리보기 열기", lambda: cmd_open(5001)),
    ("웹 대시보드 열기", lambda: cmd_open(5000)),
    ("파일 저장 시 자동 업데이트 (watch)", cmd_watch),
    ("파이 터미널 접속", cmd_ssh),
    ("마지막 업데이트 되돌리기", cmd_rollback),
    ("파이 패키지 설치 (mediapipe 등)", cmd_deps),
    ("파이 저장공간 정리 (다이어트)", cmd_clean),
]


def cmd_menu():
    while True:
        say(f"\n{C['b']}━━ AI Vision Tracker ━━{C['0']}  (Mac: {ROOT})")
        for i, (name, _) in enumerate(MENU, 1):
            say(f"  {i:>2}) {name}")
        say("   0) 종료")
        a = ask("선택: ", "0")
        if a in ("0", "q", ""):
            return 0
        try:
            fn = MENU[int(a) - 1][1]
        except (ValueError, IndexError):
            continue
        try:
            fn()
        except KeyboardInterrupt:
            say("\n(중단)", "d")
        except SystemExit:
            pass


def main(argv):
    if not argv:
        return cmd_menu()
    c, rest = argv[0], argv[1:]
    if c in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if c == "status":
        return cmd_status()
    if c in ("sync", "update", "deploy"):
        return 0 if sync(yes="--yes" in rest or "-y" in rest, dry="--dry-run" in rest) else 1
    if c == "run":
        return cmd_launch("hand", rest)
    if c == "calibrate":
        return cmd_launch("hand", ["--calibrate"] + rest)
    if c == "dashboard":
        return cmd_launch("main", rest)
    if c == "stop":
        say(remote("stop").get("raw", ""))
        return 0
    if c == "preview":
        return cmd_open(5001)
    if c == "web":
        return cmd_open(5000)
    if c == "watch":
        return cmd_watch()
    if c == "diff":
        root = choose_root()
        for f in rest or plan(root)["send"]:
            show_diff(root, f)
        return 0
    if c == "rollback":
        return cmd_rollback()
    if c == "deps":
        return cmd_deps()
    if c == "clean":
        return cmd_clean()
    if c == "ssh":
        return cmd_ssh()
    if c == "setpath":
        choose_root(force=True)
        return 0
    if c == "install":
        return cmd_install()
    print(__doc__)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]) or 0)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
