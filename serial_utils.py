"""
공통 시리얼 포트 탐색 유틸리티
motor_esp32.py 와 motor_arduino.py 에서 공유
"""
import sys
import glob


def find_port(preferred_vids: set | None = None):
    """
    시스템에서 사용 가능한 첫 번째 시리얼 포트를 반환.
    preferred_vids: 선호하는 USB VID 집합 (예: ESP32용 CP210x, CH340 등)
                    None이면 VID 필터링 없이 첫 번째 포트 반환.
    """
    if sys.platform.startswith('win'):
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            if preferred_vids:
                for p in ports:
                    if p.vid in preferred_vids:
                        return p.device
            return ports[0].device if ports else None
        except Exception:
            return None
    else:
        candidates = sorted(
            glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        )
        return candidates[0] if candidates else None
