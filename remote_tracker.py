import cv2
import time
import requests
import argparse
import os
import threading
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Laptop Remote AI Tracker for Raspberry 파이")
    parser.add_argument("--ip", type=str, default="172.30.14.31", help="라즈베리파이 IP 주소 (기본값: 172.30.14.31)")
    args = parser.parse_args()
    
    raspi_url = f"http://{args.ip}:5000"
    video_stream_url = f"{raspi_url}/video_feed"
    
    # 모델 로드 (사용자가 지정한 바탕화면 경로 - OneDrive 고려)
    desktop_paths = [
        os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\LSK0522'), 'OneDrive - 서울로봇고등학교', '바탕 화면', 'shuttlecock model', 'best_int8.tflite'),
        os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\LSK0522'), 'Desktop', 'shuttlecock model', 'best_int8.tflite')
    ]
    
    model_path = 'best_int8.tflite'
    for p in desktop_paths:
        if os.path.exists(p):
            model_path = p
            break
            
    if model_path == 'best_int8.tflite' and not os.path.exists(model_path):
        print("❌ 모델(best_int8.tflite)을 찾을 수 없습니다!")
        return
        
    print(f"[노트북] YOLO 모델 로딩 중... ({model_path})")
    try:
        model = YOLO(model_path, task='detect')
    except Exception as e:
        print(f"모델 로드 실패: {e}")
        return

    print(f"[노트북] 라즈베리파이 서버 연결 대기 중... ({raspi_url})")
    
    server_up = False
    for i in range(20):
        try:
            # 타임아웃 1초로 빠르게 서버 응답 확인
            res = requests.get(f"{raspi_url}/", timeout=1.0)
            server_up = True
            break
        except requests.exceptions.RequestException:
            pass
            
        print(f"아직 서버가 켜지지 않았습니다. 2초 후 재시도합니다... ({i+1}/20)")
        time.sleep(2)
        
    if not server_up:
        print("❌ 40초 이상 연결에 실패했습니다. 라즈베리파이 IP나 서버 상태를 확인해주세요.")
        return
        
    print("[노트북] 서버 확인 완료! 비디오 스트림을 엽니다...")
    cap = cv2.VideoCapture(video_stream_url)
    
    if not cap.isOpened():
        print("❌ 비디오 스트림을 열 수 없습니다.")
        return
        
    print("✅ 원격 추적이 시작되었습니다! 창을 닫으려면 'q'를 누르세요.")
    
    # 비동기로 API 요청을 보내기 위한 함수 (메인 루프 프레임 드랍 방지)
    def send_target(tx, ty):
        try:
            requests.get(f"{raspi_url}/set_target?tx={tx}&ty={ty}", timeout=0.1)
        except requests.exceptions.RequestException:
            pass
            
    frame_count = 0
    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("스트림이 끊겼습니다. 재연결을 시도합니다...")
            time.sleep(1)
            cap.open(video_stream_url)
            continue
            
        # 노트북의 빠른 CPU/GPU로 YOLO 연산 (초당 수십 프레임)
        results = model(frame, verbose=False, conf=0.25)
        
        target_found = False
        if len(results) > 0 and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            best_box = None
            max_conf = -1
            
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0])
                if cls_id == 0 and conf > max_conf:  # 0번 클래스(shuttlecock)
                    max_conf = conf
                    best_box = box
                    
            if best_box is not None:
                x1, y1, x2, y2 = map(int, best_box.xyxy[0])
                tx = (x1 + x2) // 2
                ty = (y1 + y2) // 2
                
                # 라즈베리파이로 목표 좌표 전송 (비동기)
                threading.Thread(target=send_target, args=(tx, ty), daemon=True).start()
                
                # 화면에 BBox 그리기
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(frame, (tx, ty), 5, (0, 0, 255), -1)
                cv2.putText(frame, f"Shuttlecock {max_conf:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                target_found = True
                
        # 타겟을 못 찾았을 경우, 빈 좌표를 보내지 않고 가만히 둠.
        # 라즈베리파이는 2초간 통신이 없으면 자동으로 원격모드를 해제함.
        
        # FPS 계산 및 표시
        frame_count += 1
        elapsed = time.time() - start_time
        fps = frame_count / elapsed
        if frame_count % 30 == 0:
            start_time = time.time()
            frame_count = 0
            
        cv2.putText(frame, f"Laptop FPS: {fps:.1f}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(frame, "REMOTE TRACKING", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
        cv2.imshow("Laptop AI Tracker", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
