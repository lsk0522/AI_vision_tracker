#!/usr/bin/env python3
"""
AI Vision Tracker — 라즈베리파이 쪽 도우미. Mac 의 aivt.py 가 ssh 로 자동 설치/호출합니다.
(직접 실행할 일은 거의 없습니다. 위치: ~/.aivt/remote.py)

  locate                    코드 위치/실행 상태를 JSON 으로
  manifest ROOT             동기화 대상 파일들의 sha256 목록 (JSON)
  apply ROOT                stdin 의 tar 를 적용 (기존 파일 백업 → 덮어쓰기 → 기록)
  rollback ROOT             마지막 적용 취소 (백업 복원 + 새로 생긴 파일 삭제)
  launch ROOT hand|main ... 손 추적기 / 웹 대시보드 실행 (가상환경 자동)
  stop                      실행 중인 main.py / hand_tracker.py 정지 (Ctrl+C 신호)
"""
import glob
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import time

AIVT = os.path.expanduser("~/.aivt")
STATE = os.path.join(AIVT, "state.json")
BACKUPS = os.path.join(AIVT, "backups")
KEEP_BACKUPS = 10

SYNC_DIRS = ("backend", "scripts", "firmware")
EXCL_DIRS = {"__pycache__", ".venv", "venv", "node_modules", ".git", "picture",
             "learning_data", ".vscode", ".idea", "scratch"}
EXCL_FILES = {".DS_Store", "hand_tracker_calib.json", "Thumbs.db"}
EXCL_SUFFIX = (".pyc", ".log", ".part", ".swp")


def excluded(name, is_dir):
    if is_dir:
        return name in EXCL_DIRS or name.startswith(".")
    return name in EXCL_FILES or name.startswith("._") or name.endswith(EXCL_SUFFIX)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest(root):
    out = {}
    for top in SYNC_DIRS:
        base = os.path.join(root, top)
        for dp, dns, fns in os.walk(base):
            dns[:] = sorted(d for d in dns if not excluded(d, True))
            for fn in sorted(fns):
                if excluded(fn, False):
                    continue
                p = os.path.join(dp, fn)
                if os.path.islink(p) or not os.path.isfile(p):
                    continue
                out[os.path.relpath(p, root).replace(os.sep, "/")] = sha256(p)
    return out


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(st):
    os.makedirs(AIVT, exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def pids(pattern_names):
    """cmdline 에 주어진 스크립트 이름이 들어간 python 프로세스 pid."""
    res = []
    me = os.getpid()
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == me:
            continue
        try:
            with open(f"/proc/{d}/cmdline", "rb") as f:
                args = [a.decode(errors="ignore") for a in f.read().split(b"\0") if a]
        except OSError:
            continue
        if not args or "python" not in os.path.basename(args[0]):
            continue
        if any(os.path.basename(a) in pattern_names for a in args[1:3]):
            res.append(int(d))
    return res


def proc_cwd(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


def venv_python(root, what="main"):
    """hand: 손 추적 전용 backend/.venv 우선 (main.py 환경을 건드리지 않기 위해)
       main: 기존 .venv 우선"""
    order = [os.path.join(root, "backend", ".venv"), os.path.join(root, ".venv")]
    if what != "hand":
        order.reverse()
        # backend/main.py 는 flask + mediapipe 가 필요 → flask 가 깔린 가상환경을 먼저
        has_flask = lambda c: bool(glob.glob(os.path.join(c, "lib", "python*", "site-packages", "flask")))
        order.sort(key=lambda c: not has_flask(c))
    for c in order + [os.path.join(os.path.dirname(root), ".venv")]:
        p = os.path.join(c, "bin", "python")
        if os.path.exists(p):
            return p
    return sys.executable or "python3"


def cmd_locate():
    """후보: 1) 실행 중 main.py 의 폴더  2) ~/ 아래 backend/motor_esp32.py  3) 다른 구조"""
    cands = []
    for pid in pids({"main.py"}):
        cwd = proc_cwd(pid)
        if cwd and os.path.exists(os.path.join(cwd, "motor_esp32.py")):
            cands.append(("running", cwd))
    home = os.path.expanduser("~")
    for dp, dns, fns in os.walk(home):
        depth = dp[len(home):].count(os.sep)
        dns[:] = [d for d in dns if not (d.startswith(".") or d in EXCL_DIRS or d == "site-packages")]
        if depth >= 4:
            dns[:] = []
        if "motor_esp32.py" in fns and "state.py" in fns:
            cands.append(("found", dp))
    seen, out = set(), []
    for kind, d in cands:
        if d in seen:
            continue
        seen.add(d)
        is_backend = os.path.basename(d) == "backend"
        root = os.path.dirname(d) if is_backend else None
        out.append({"code_dir": d, "kind": kind, "root": root,
                    "git": bool(root and os.path.isdir(os.path.join(root, ".git"))),
                    "mtime": os.path.getmtime(os.path.join(d, "motor_esp32.py"))})
    st = load_state()
    print(json.dumps({
        "home": home, "candidates": out,
        "running": {"main": pids({"main.py"}), "hand": pids({"hand_tracker.py"})},
        "last_sync": {k: st.get(k) for k in ("time", "version", "from", "root")},
        "python": sys.version.split()[0],
    }, ensure_ascii=False))


def cmd_manifest(root):
    st = load_state()
    synced = st.get("manifest", {}) if st.get("root") == root else {}
    print(json.dumps({"root": root, "exists": os.path.isdir(root), "files": manifest(root),
                      "synced": synced, "version": st.get("version") if synced else None,
                      "running": {"main": pids({"main.py"}), "hand": pids({"hand_tracker.py"})},
                      "venv": venv_python(root, "hand")}, ensure_ascii=False))


def _safe_members(tf):
    for m in tf.getmembers():
        n = m.name
        if n.startswith("/") or ".." in n.split("/") or not (m.isfile() or m.isdir()):
            raise SystemExit(f"거부: 안전하지 않은 경로 {n}")
        if n != ".aivt_meta.json" and n.split("/")[0] not in SYNC_DIRS:
            raise SystemExit(f"거부: 동기화 대상이 아닌 경로 {n}")
    return tf.getmembers()


def cmd_apply(root):
    data = sys.stdin.buffer.read()
    tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
    members = _safe_members(tf)
    meta = json.loads(tf.extractfile(".aivt_meta.json").read().decode()) \
        if ".aivt_meta.json" in tf.getnames() else {}
    files = [m for m in members if m.isfile() and m.name != ".aivt_meta.json"]

    # 1) 덮어쓸 기존 파일 백업
    os.makedirs(BACKUPS, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    bpath = os.path.join(BACKUPS, f"{ts}.tgz")
    n = 1
    while os.path.exists(bpath):          # 같은 순간 두 번 적용돼도 백업이 겹치지 않게
        bpath = os.path.join(BACKUPS, f"{ts}-{n}.tgz")
        n += 1
    added = []
    with tarfile.open(bpath, "w:gz") as bt:
        for m in files:
            p = os.path.join(root, m.name)
            if os.path.isfile(p):
                bt.add(p, arcname=m.name)
            else:
                added.append(m.name)
        info = json.dumps({"root": root, "added": added, "time": ts}).encode()
        ti = tarfile.TarInfo(".aivt_backup.json")
        ti.size = len(info)
        bt.addfile(ti, io.BytesIO(info))

    # 2) 적용 (임시 파일에 쓰고 교체 → 중간에 끊겨도 반쯤 쓴 파일이 남지 않음)
    for m in files:
        dst = os.path.join(root, m.name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".aivt-tmp"
        with open(tmp, "wb") as f:
            f.write(tf.extractfile(m).read())
        os.chmod(tmp, m.mode & 0o777 or 0o644)
        os.replace(tmp, dst)

    # 3) 기록
    st = load_state()
    synced = st.get("manifest", {}) if st.get("root") == root else {}
    synced.update(meta.get("sent", {}))
    st.update({"root": root, "manifest": synced, "version": meta.get("version"),
               "time": time.strftime("%Y-%m-%d %H:%M:%S"), "from": meta.get("from")})
    hist = st.setdefault("history", [])
    hist.append({"time": st["time"], "version": st["version"], "files": len(files), "backup": bpath})
    st["history"] = hist[-30:]
    save_state(st)

    olds = sorted(f for f in os.listdir(BACKUPS) if f.endswith(".tgz"))
    for f in olds[:-KEEP_BACKUPS]:
        os.remove(os.path.join(BACKUPS, f))
    print(json.dumps({"ok": True, "written": len(files), "added": len(added), "backup": bpath}))


def cmd_rollback(root):
    olds = sorted(f for f in os.listdir(BACKUPS) if f.endswith(".tgz")) if os.path.isdir(BACKUPS) else []
    if not olds:
        print(json.dumps({"ok": False, "error": "백업이 없습니다"}))
        return
    bpath = os.path.join(BACKUPS, olds[-1])
    with tarfile.open(bpath, "r:gz") as bt:
        info = json.loads(bt.extractfile(".aivt_backup.json").read().decode())
        if info.get("root") != root:
            print(json.dumps({"ok": False, "error": f"백업 위치가 다릅니다: {info.get('root')}"}))
            return
        restored = 0
        for m in bt.getmembers():
            if m.name == ".aivt_backup.json" or not m.isfile():
                continue
            if m.name.startswith("/") or ".." in m.name.split("/"):
                continue
            dst = os.path.join(root, m.name)
            tmp = dst + ".aivt-tmp"
            with open(tmp, "wb") as f:
                f.write(bt.extractfile(m).read())
            os.chmod(tmp, m.mode & 0o777 or 0o644)
            os.replace(tmp, dst)
            restored += 1
    removed = 0
    for rel in info.get("added", []):
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            os.remove(p)
            removed += 1
    os.remove(bpath)
    st = load_state()
    if st.get("root") == root:
        st["manifest"] = manifest(root)   # 되돌린 현재 상태를 '마지막 동기화' 로
        st["version"] = "rollback"
        st["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_state(st)
    print(json.dumps({"ok": True, "restored": restored, "removed": removed, "backup": bpath}))


def _stop(names, wait=6.0):
    ps = pids(names)
    for p in ps:
        try:
            os.kill(p, signal.SIGINT)
        except OSError:
            pass
    end = time.time() + wait
    while time.time() < end and pids(names):
        time.sleep(0.2)
    left = pids(names)
    for p in left:
        try:
            os.kill(p, signal.SIGTERM)
        except OSError:
            pass
    return ps


def cmd_stop():
    ps = _stop({"main.py", "hand_tracker.py"})
    print("정지함: " + (", ".join(map(str, ps)) if ps else "실행 중인 것 없음"))


def cmd_launch(root, what, args):
    code = os.path.join(root, "backend")
    py = venv_python(root, what)
    script = "hand_tracker.py" if what == "hand" else "main.py"
    if not os.path.exists(os.path.join(code, script)):
        raise SystemExit(f"❌ {code}/{script} 가 없습니다. 먼저 업데이트(동기화)를 하세요.")
    other = {"main.py"} if what == "hand" else {"hand_tracker.py"}
    same = {script}
    running_other, running_same = pids(other), pids(same)
    if running_other or running_same:
        names = ", ".join(sorted((other if running_other else set()) | (same if running_same else set())))
        print(f"⚠ 이미 실행 중: {names} — 카메라/ESP32 를 같이 쓸 수 없어 먼저 정지합니다.")
        _stop(other | same)
    if what == "hand":
        chk = subprocess.run([py, "-c", "import mediapipe"], capture_output=True)
        if chk.returncode != 0:
            raise SystemExit("❌ 파이에 mediapipe 가 없습니다. Mac 터미널에서  aivt deps  를 실행하세요.")
    os.chdir(code)
    print(f"▶ {py} {script} {' '.join(args)}   ({code})", flush=True)
    os.execv(py, [py, script] + list(args))


# ──────────────────────────── 공간 정리 ────────────────────────────
def dir_size(path):
    total = 0
    if os.path.isfile(path):
        return os.path.getsize(path)
    for dp, dns, fns in os.walk(path, onerror=lambda e: None):
        for fn in fns:
            try:
                st = os.lstat(os.path.join(dp, fn))
                total += st.st_blocks * 512 if hasattr(st, "st_blocks") else st.st_size
            except OSError:
                pass
    return total


def _du_m(path, timeout=120):
    try:
        out = subprocess.run(["du", "-sxm", path], capture_output=True, text=True, timeout=timeout).stdout
        return int(out.split()[0]) * 1024 * 1024
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


# 머리 없는(모니터 없는) 로봇에서 보통 필요 없는 큰 패키지
BLOAT_PKGS = ["wolfram-engine", "libreoffice*", "sonic-pi", "scratch*", "minecraft-pi", "nuscratch",
              "smartsim", "penguinspuzzle", "geany", "thonny", "claws-mail", "bluej", "greenfoot*",
              "code-the-classics", "realvnc-vnc-viewer", "mathematica-fonts", "chromium-browser-l10n"]


def cmd_scan(root):
    home = os.path.expanduser("~")
    items = []

    def add(iid, cat, title, paths, note="", default=False, sudo=False, backup=False, size=None):
        paths = [p for p in paths if os.path.exists(p)] if not sudo else paths
        if not paths and not sudo:
            return
        sz = size if size is not None else sum(dir_size(p) for p in paths)
        if sz is None or sz < 1024 * 1024:   # 1MB 미만은 생략
            return
        items.append({"id": iid, "cat": cat, "title": title, "paths": paths, "size": sz, "note": note,
                      "default": default, "sudo": sudo, "backup": backup})

    # ── 캐시 (지워도 안전) ──
    add("pip", "cache", "pip 다운로드 캐시", [f"{home}/.cache/pip"], default=True)
    others = [os.path.join(home, ".cache", d) for d in (os.listdir(f"{home}/.cache") if os.path.isdir(f"{home}/.cache") else [])
              if d != "pip"]
    add("cache", "cache", "기타 사용자 캐시 (~/.cache)", others, "브라우저·썸네일 캐시 등, 필요하면 다시 생김", default=True)
    add("wheels", "cache", "실패한 패키지 전송 찌꺼기", [f"{AIVT}/wheels"], default=True)
    add("trash", "cache", "휴지통", [f"{home}/.local/share/Trash"], default=True)
    pyc = []
    for base in (home,):
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in (".venv", "venv", "site-packages", ".git", "node_modules")
                      and not (dp == home and d.startswith("."))]
            if os.path.basename(dp) == "__pycache__":
                pyc.append(dp)
                dns[:] = []
    add("pycache", "cache", "파이썬 컴파일 캐시 (__pycache__)", pyc, f"{len(pyc)}개 폴더", default=True)
    # VS Code 원격(SSH) 접속이 남긴 것 — 확장 설치파일 캐시, 예전 서버 버전
    vs = f"{home}/.vscode-server"
    add("vscode_vsix", "cache", "VS Code 원격 확장 설치파일 캐시", [f"{vs}/data/CachedExtensionVSIXs"],
        "설치된 확장은 그대로", default=True)
    try:
        with open(f"{vs}/cli/servers/lru.json") as f:
            lru = json.load(f)
        old_srv = [f"{vs}/cli/servers/{s}" for s in lru[1:] if "/" not in s and s]
    except (OSError, ValueError, TypeError):
        old_srv = []
    add("vscode_old", "cache", "VS Code 원격 서버 예전 버전", old_srv, "최신 버전 1개는 남김", default=True)
    # 이 파이(arm)에 설치할 수 없는 x86 설치 파일
    debs = []
    for d in (f"{home}/Downloads", f"{home}/다운로드"):
        if os.path.isdir(d):
            debs += [os.path.join(d, n) for n in os.listdir(d) if n.endswith(("_amd64.deb", "_i386.deb"))]
    add("x86deb", "cache", "x86 용 설치 파일 (~/Downloads/*_amd64.deb)", debs, "이 파이(ARM)에서는 설치 불가",
        default=True)
    add("vscode_all", "code", "VS Code 원격 서버 전체 (~/.vscode-server)", [vs],
        "⚠ VS Code 로 파이에 원격 접속하면 다시 설치됨 (확장도 다시 받음)")
    add("apt", "cache", "apt 패키지 캐시 (/var/cache/apt)", ["/var/cache/apt/archives"], default=True, sudo=True,
        size=dir_size("/var/cache/apt/archives"))
    jr = subprocess.run(["journalctl", "--disk-usage"], capture_output=True, text=True)
    jsz = None
    for tok in jr.stdout.replace(",", " ").split():
        try:
            mult = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30}[tok[-1].upper()]
            jsz = int(float(tok[:-1]) * mult)
        except (KeyError, ValueError, IndexError):
            continue
    add("journal", "cache", "시스템 로그 (50MB 만 남김)", ["journal"], default=True, sudo=True,
        size=(jsz - 50 * (1 << 20)) if jsz else None)

    # ── 파이에서 안 쓰는 코드/자료 (Mac 으로 백업 후 삭제) ──
    if root and os.path.isdir(root):
        add("raspi_main", "code", "옛 사본 폴더 raspi_main/", [f"{root}/raspi_main"],
            "backend/ 와 중복 (가상환경 .venv 는 백업 안 함 — 다른 기기에선 못 씀)", backup=True)
        add("website", "code", "웹사이트 소스 website/", [f"{root}/website"], "GitHub Pages 용, 파이에서 안 씀", backup=True)
        add("hardware", "code", "3D 모델 hardware/", [f"{root}/hardware"], "파이에서 안 씀", backup=True)
        add("archive", "code", "옛 버전 보관 archive/", [f"{root}/archive"], backup=True)
        add("docs", "code", "문서 docs/", [f"{root}/docs"], "Mac 에 원본 있음", backup=True)
        add("scratch", "code", "실험 파일 scratch/", [f"{root}/scratch", f"{root}/scratch.py"], backup=True)
        add("git", "code", "git 기록 .git/", [f"{root}/.git"], "aivt 로 업데이트하면 필요 없음 (update.sh 는 못 씀)",
            backup=True)
        flat = [os.path.join(root, n) for n in os.listdir(root)
                if n not in ("backend", "scripts", "firmware", "data", ".venv", ".git", "raspi_main", "website",
                             "hardware", "archive", "docs", "scratch", "scratch.py")
                and (n.endswith((".py", ".tflite", ".pt", ".sh", ".md", ".txt", ".png", ".patch"))
                     or n in ("routes", "static", "templates", "esp32_firmware", "esp32_firmware_backup",
                              "models", "learning_data"))]
        add("flat", "code", "옛 구조 코드 (폴더 최상위의 main.py 등)", flat,
            "⚠ 지금 쓰던 대시보드. aivt dashboard(새 코드)가 잘 되는지 확인 후 지우기", backup=True)
        add("pictures", "data", "캡처 사진 (data/picture)", [f"{root}/data/picture", f"{root}/picture"], backup=True)
    add("old_ver", "code", "예전 버전 ~/Old_Ver", [f"{home}/Old_Ver"], backup=True)

    # ── 불필요한 시스템 패키지 ──
    try:
        out = subprocess.run(["dpkg-query", "-Wf", "${Installed-Size}\t${Package}\t${Status}\n"],
                             capture_output=True, text=True, timeout=30).stdout
        inst = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and "installed" in parts[2] and parts[0].isdigit():
                inst[parts[1]] = int(parts[0]) * 1024
        import fnmatch
        for pat in BLOAT_PKGS:
            names = sorted(n for n in inst if fnmatch.fnmatch(n, pat))
            if names:
                add("pkg:" + pat, "system", f"패키지 {pat.rstrip('*')}" + (" 등" if len(names) > 1 else ""),
                    names, "모니터 없이 쓰는 로봇에선 보통 불필요", sudo=True, size=sum(inst[n] for n in names))
        top = sorted(inst.items(), key=lambda kv: -kv[1])[:12]
    except (OSError, subprocess.SubprocessError):
        top = []

    st = os.statvfs(home)
    tops = {}
    for d in ("/usr", "/var", "/opt", "/home", "/tmp", "/swapfile", "/var/swap"):
        if os.path.exists(d):
            tops[d] = _du_m(d)
    print(json.dumps({"free": st.f_bavail * st.f_frsize, "total": st.f_blocks * st.f_frsize,
                      "items": items, "top_pkgs": top, "tops": tops}, ensure_ascii=False))


def cmd_delete():
    """stdin 의 JSON 경로 목록 삭제 (홈 폴더 아래만 허용)."""
    import shutil
    paths = json.loads(sys.stdin.read() or "[]")
    home = os.path.realpath(os.path.expanduser("~"))
    done, skipped = 0, []
    for p in paths:
        rp = os.path.realpath(p)
        if not rp.startswith(home + os.sep) or rp in (home, os.path.join(home, ".aivt")):
            skipped.append(p)
            continue
        try:
            if os.path.isdir(rp) and not os.path.islink(p):
                shutil.rmtree(rp)
            else:
                os.remove(p)
            done += 1
        except OSError as e:
            skipped.append(f"{p} ({e})")
    st = os.statvfs(home)
    print(json.dumps({"ok": True, "deleted": done, "skipped": skipped, "free": st.f_bavail * st.f_frsize},
                     ensure_ascii=False))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    c, a = sys.argv[1], sys.argv[2:]
    if c == "locate":
        cmd_locate()
    elif c == "manifest":
        cmd_manifest(a[0])
    elif c == "apply":
        cmd_apply(a[0])
    elif c == "rollback":
        cmd_rollback(a[0])
    elif c == "stop":
        cmd_stop()
    elif c == "launch":
        cmd_launch(a[0], a[1], a[2:])
    elif c == "scan":
        cmd_scan(a[0] if a else None)
    elif c == "delete":
        cmd_delete()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
