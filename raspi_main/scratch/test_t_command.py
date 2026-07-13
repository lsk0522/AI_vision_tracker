import sys
import os
import time
import serial

# Add parent directory to path so we can import serial_utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import serial_utils

def test():
    print("Finding serial port...")
    port = serial_utils.find_port()
    if not port:
        print("[-] No serial port found!")
        return
    print(f"[+] Found serial port: {port}")
    
    print("Connecting to serial port at 115200 baud...")
    ser = serial.Serial(port, 115200, timeout=1.0)
    time.sleep(2.0) # Wait for reboot
    
    # Read boot lines
    if ser.in_waiting:
        print("[Boot Info]", ser.read(ser.in_waiting).decode('utf-8', errors='ignore'))
        
    print("[+] Sending MODE:TRACK...")
    ser.write(b"MODE:TRACK\n")
    time.sleep(0.1)
    if ser.in_waiting:
        print("[Response]", ser.read(ser.in_waiting).decode('utf-8', errors='ignore'))
        
    print("[+] Sending T:450:300 (which should move the motor Pan/Tilt)...")
    ser.write(b"T:450:300\n")
    
    # Monitor response for 5 seconds
    start_time = time.time()
    while time.time() - start_time < 5.0:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            print(f"[ESP32] {line}")
        time.sleep(0.01)
        
    print("[+] Test completed.")
    ser.close()

if __name__ == '__main__':
    test()
