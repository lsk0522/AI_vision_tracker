import atexit
import signal
import sys
import socket

from flask import Flask
from routes import setup_routes
import detector
import motor_esp32
import motor_arduino
import state
import cli_ui

def get_local_ip():
    """자신의 실제 로컬 네트워크 IP를 가져옵니다."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 구글 퍼블릭 DNS로 더미 연결을 시도하여 자신의 실제 라우팅 IP를 알아냄
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


_cleaned_up = False


def _cleanup_motors():
    """프로그램 종료 시 모터 홀딩 전류 해제 후 안전하게 종료."""
    global _cleaned_up
    if _cleaned_up:
        return
    _cleaned_up = True
    
    # TUI가 켜져있다면 중지하여 터미널 원래 상태 복구
    import cli_ui
    cli_ui.stop_tui()
    
    print("\n[main] 종료 시그널 수신 — 모터 해제 중...")
    try:
        if state.device_type == "arduino":
            motor_arduino.estop()
        else:
            motor_esp32.release_motors()
    except Exception:
        pass
    try:
        motor_esp32.safe_disconnect()
    except Exception:
        pass
    try:
        motor_arduino.safe_disconnect()
    except Exception:
        pass
    print("[main] 모터 해제 완료. 종료합니다.")


def _shutdown(signum=None, frame=None):
    _cleanup_motors()
    sys.exit(0)


# 정상/비정상 종료 모두 대응
atexit.register(_cleanup_motors)
signal.signal(signal.SIGINT,  _shutdown)   # Ctrl+C
signal.signal(signal.SIGTERM, _shutdown)   # 프로세스 kill


import cli_ui

app = Flask(__name__)
setup_routes(app)

# 하드웨어 초기화 (CLI 로딩 시퀀스 내부에서 실행되는 것처럼 딜레이 적용)
cli_ui.run_loading_sequence()

# TUI 대시보드 스레드 시작 (이후의 print()는 모두 가로채짐)
cli_ui.start_tui()

detector.start()
motor_esp32.start()   # ESP32 연결
motor_arduino.start() # Arduino 연결

    local_ip = get_local_ip()
    print("✔ All systems go!")
    print(f"=> Web Dashboard is available at: http://{local_ip}:5000/")
    print("Press Ctrl+C to quit")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
