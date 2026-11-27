#!/usr/bin/env python3
"""
라즈베리파이 IP 자동 탐색기 (표준 라이브러리만 사용, Mac/Linux/Windows 공용)

IP가 바뀌어도 아래 순서로 파이를 찾아 IP 한 줄을 출력합니다.
  1) 환경변수 PI_HOST 가 있으면 그대로 사용
  2) 마지막으로 찾은 IP (캐시) 가 아직 파이인지 확인
  3) mDNS 호스트명 (<hostname>.local)
  4) 내 컴퓨터가 속한 /24 대역 + 마지막 IP의 /24 대역을 스캔 (SSH 22번 포트)

"이게 내 파이가 맞나?" 확인은 SSH 호스트 키로 합니다.
--pin 으로 한 번 고정해 두면, 같은 대역의 다른 리눅스 장비와 헷갈리지 않습니다.

사용법:
  python3 scripts/find_pi.py            # IP 출력 (못 찾으면 종료코드 1)
  python3 scripts/find_pi.py --pin      # 지금 찾은 파이의 호스트 키/호스트명 고정
  python3 scripts/find_pi.py --pin --ip 10.195.251.19
  python3 scripts/find_pi.py --show     # 저장된 설정 보기
"""
import argparse
import concurrent.futures as cf
import ipaddress
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

STATE_PATH = Path(os.environ.get(
    "AIVT_STATE", Path.home() / ".config" / "ai_vision_tracker" / "pi.json"))

DEFAULTS = {
    "user": "pi30306",
    "hostname": "raspberrypi",
    "ip": "10.195.251.19",   # 마지막으로 알려진 IP (자동 갱신됨)
    "hostkey": None,         # "ssh-ed25519 AAAA..." (--pin 으로 저장)
}


def log(*a):
    print("[find_pi]", *a, file=sys.stderr)


def load_state():
    st = dict(DEFAULTS)
    try:
        st.update(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return st


def save_state(st):
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        log("설정 저장 실패:", e)


# ---------- 확인 함수 ----------

def port_open(ip, port=22, timeout=0.5):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def ssh_banner(ip, timeout=1.5):
    try:
        with socket.create_connection((ip, 22), timeout=timeout) as s:
            s.settimeout(timeout)
            return s.recv(256).decode(errors="ignore").strip()
    except OSError:
        return ""


def ssh_hostkey(ip, timeout=3):
    """ssh-keyscan 으로 ed25519 호스트 키를 가져옴. 없으면 None."""
    exe = shutil.which("ssh-keyscan")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-T", str(timeout), "-t", "ed25519", ip],
                             capture_output=True, text=True, timeout=timeout + 3).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        if line and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 3:
                return f"{parts[1]} {parts[2]}"
    return None


def is_my_pi(ip, st, timeout=0.6):
    if not ip or not port_open(ip, 22, timeout):
        return False
    if st.get("hostkey"):
        return ssh_hostkey(ip) == st["hostkey"]
    # 아직 고정 안 했으면: 데비안 계열 SSH 서버인지만 확인 (Raspberry Pi OS = Debian)
    b = ssh_banner(ip)
    return "Debian" in b or "Raspbian" in b


# ---------- 내 네트워크 대역 ----------

def local_ipv4s():
    ips = set()
    for target in ("10.255.255.255", "192.168.255.255", "8.8.8.8"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((target, 1))
            ips.add(s.getsockname()[0])
            s.close()
        except OSError:
            pass
    if platform.system() == "Darwin":
        for iface in ("en0", "en1", "en2"):
            try:
                out = subprocess.run(["ipconfig", "getifaddr", iface],
                                     capture_output=True, text=True, timeout=2).stdout.strip()
                if out:
                    ips.add(out)
            except (OSError, subprocess.SubprocessError):
                pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith(("127.", "169.254.", "0.")))


def scan(st):
    nets = set()
    for ip in local_ipv4s() + ([st["ip"]] if st.get("ip") else []):
        try:
            nets.add(ipaddress.ip_network(f"{ip}/24", strict=False))
        except ValueError:
            pass
    if not nets:
        return []
    log("스캔 대역:", ", ".join(str(n) for n in sorted(nets)))
    hosts = [str(h) for n in nets for h in n.hosts()]
    with cf.ThreadPoolExecutor(max_workers=128) as ex:
        open22 = [h for h, ok in zip(hosts, ex.map(lambda h: port_open(h, 22, 0.4), hosts)) if ok]
    log(f"SSH 열린 장비 {len(open22)}대")
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        return [h for h, ok in zip(open22, ex.map(lambda h: is_my_pi(h, st, 1.0), open22)) if ok]


# ---------- 메인 로직 ----------

def resolve(st, allow_scan=True):
    env = os.environ.get("PI_HOST")
    if env:
        return env

    if is_my_pi(st.get("ip"), st):
        return st["ip"]

    for name in (f"{st['hostname']}.local", st["hostname"]):
        try:
            ip = socket.gethostbyname(name)
        except OSError:
            continue
        if is_my_pi(ip, st):
            log(f"mDNS/DNS로 찾음: {name} -> {ip}")
            return ip

    if not allow_scan:
        return None

    found = scan(st)
    if len(found) == 1 or (found and st.get("hostkey")):
        return found[0]
    if len(found) > 1:
        # 호스트 키 고정 전이면 Flask(5000) 가 떠 있는 쪽을 우선
        flask = [h for h in found if port_open(h, 5000, 0.5)]
        if len(flask) == 1:
            return flask[0]
        log("후보가 여러 대입니다:", ", ".join(found))
        log("맞는 IP로 한 번 고정하세요: python3 scripts/find_pi.py --pin --ip <IP>")
    return None


def pin(st, ip):
    key = ssh_hostkey(ip)
    if not key:
        log(f"{ip} 에서 SSH 호스트 키를 못 가져왔습니다.")
        return False
    st["hostkey"] = key
    st["ip"] = ip
    try:
        name = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             "-o", "StrictHostKeyChecking=accept-new", f"{st['user']}@{ip}", "hostname"],
            capture_output=True, text=True, timeout=10).stdout.strip()
        if name:
            st["hostname"] = name
    except (OSError, subprocess.SubprocessError):
        pass
    save_state(st)
    log(f"고정 완료: {ip} (hostname={st['hostname']})")
    return True


def find_pi(allow_scan=True):
    """다른 파이썬 코드에서 import 해서 쓰는 함수. 못 찾으면 None."""
    st = load_state()
    ip = resolve(st, allow_scan)
    if ip and ip != st.get("ip") and not os.environ.get("PI_HOST"):
        log(f"IP 변경 감지: {st.get('ip')} -> {ip}")
        st["ip"] = ip
        save_state(st)
    return ip


def main():
    p = argparse.ArgumentParser(description="라즈베리파이 IP 자동 탐색")
    p.add_argument("--pin", action="store_true", help="찾은(또는 --ip) 파이의 호스트 키를 고정")
    p.add_argument("--ip", help="--pin 과 함께: 이 IP를 내 파이로 고정")
    p.add_argument("--user", help="SSH 사용자명 저장 (기본 pi30306)")
    p.add_argument("--no-scan", action="store_true", help="대역 스캔 생략 (빠름)")
    p.add_argument("--show", action="store_true", help="저장된 설정 출력")
    a = p.parse_args()

    st = load_state()
    if a.user:
        st["user"] = a.user
        save_state(st)
    if a.show:
        print(json.dumps({**st, "_path": str(STATE_PATH)}, indent=2, ensure_ascii=False))
        return 0

    if a.pin:
        ip = a.ip or resolve(st, not a.no_scan)
        if not ip:
            log("파이를 찾지 못해 고정할 수 없습니다. --ip 로 직접 지정하세요.")
            return 1
        if not pin(st, ip):
            return 1
        print(ip)
        return 0

    ip = find_pi(not a.no_scan)
    if not ip:
        log("라즈베리파이를 찾지 못했습니다.")
        log("  - 파이 전원/네트워크 확인, Pi Connect 셸에서 `hostname -I` 로 IP 확인")
        log("  - 찾은 IP로: python3 scripts/find_pi.py --pin --ip <IP>")
        return 1
    print(ip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
