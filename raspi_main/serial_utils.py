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
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            return None
            
        if preferred_vids:
            for p in ports:
                if p.vid in preferred_vids:
                    return p.device
                    
        # 선호하는 VID가 없거나 일치하는 게 없으면 첫 번째 포트 반환
        return ports[0].device
    except Exception as e:
        print(f"[serial_utils] 탐색 에러: {e}")
        return None
