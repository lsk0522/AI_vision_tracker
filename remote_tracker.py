import cv2
import time
import requests
import argparse
import os
import threading
import numpy as np
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Laptop Remote AI Tracker for Raspberry 파이")
    parser.add_argument("--ip", type=str, default="172.30.14.31", help="라즈베리파이 IP 주소 (기본값: 172.30.14.31)")
    args = parser.parse_args()
    
    raspi_url = f"http://{args.ip}:5000"
    video_stream_url = f"{raspi_url}/video"
    
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
        
    # 비동기로 프레임 읽기 (버퍼 밀림 방지 및 지연 최소화)
    class VideoCaptureThread:
        def __init__(self, url):
            self.cap = cv2.VideoCapture(url)
            self.ret, self.frame = self.cap.read()
            self.running = True
            self.lock = threading.Lock()
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()

        def update(self):
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.ret = ret
                        self.frame = frame
                else:
                    if not self.running:
                        break
                    # 끊겼을 때 재연결 로직
                    time.sleep(1)
                    if not self.running:
                        break
                    self.cap.open(video_stream_url)

        def read(self):
            with self.lock:
                return self.ret, (self.frame.copy() if self.frame is not None else None)

        def release(self):
            self.running = False
            self.cap.release()  # 먼저 release하여 cap.read() 블로킹을 해제
            try:
                self.thread.join(timeout=1.0)  # 스레드 종료 대기 (최대 1초)
            except:
                pass

    print("[노트북] 서버 확인 완료! 비디오 스트림을 엽니다...")
    cap = VideoCaptureThread(video_stream_url)
    
    if not cap.cap.isOpened():
        print("❌ 비디오 스트림을 열 수 없습니다.")
        return
        
    print("✅ 원격 추적이 시작되었습니다! 창을 닫으려면 'q'를 누르세요.")
    
    # 비동기로 API 요청을 보내기 위한 함수 (메인 루프 프레임 드랍 방지)
    _paused = False
    _paused_lock = threading.Lock()
    
    # 0.3초마다 라즈베리파이의 모드(Auto/Manual) 상태를 체크하는 독립 스레드
    # YOLO 검출 성공 여부와 상관없이 모드 전환을 즉각 감지하기 위함
    def poll_status():
        nonlocal _paused
        while True:
            try:
                resp = requests.get(f"{raspi_url}/tracking_status", timeout=0.5)
                data = resp.json()
                with _paused_lock:
                    _paused = (data.get("control_mode") != "auto")
            except:
                pass
            time.sleep(0.3)

    threading.Thread(target=poll_status, daemon=True).start()
    
    def send_target(tx, ty):
        try:
            requests.get(f"{raspi_url}/set_target?tx={tx}&ty={ty}", timeout=0.2)
        except requests.exceptions.RequestException:
            pass
            
    frame_count = 0
    start_time = time.time()
    
    while True:
        # 라즈베리파이가 수동(조이스틱) 모드이면 비디오 스트림까지 완전 해제
        with _paused_lock:
            is_paused = _paused
        if is_paused:
            # 비디오 스트림 연결을 완전히 끊어서 라즈베리파이 부하를 0으로 만듦
            if cap is not None:
                print("[노트북] 조이스틱 모드 감지 → 비디오 스트림 해제 (라즈베리파이 부하 제거)")
                cap.release()
                cap = None
            
            # PAUSED 표시 (검은 화면)
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "PAUSED (Joystick mode)", (120, 230), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 165, 255), 2)
            cv2.putText(blank, "Waiting for Auto mode...", (140, 270), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 1)
            cv2.imshow("Laptop AI Tracker", blank)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            time.sleep(0.2)
            continue
        
        # auto 모드로 복귀 시 비디오 스트림 재연결
        if cap is None:
            print("[노트북] Auto 모드 복귀 → 비디오 스트림 재연결 중...")
            cap = VideoCaptureThread(video_stream_url)
            time.sleep(0.5)
            print("[노트북] 재연결 완료! AI 추적을 재개합니다.")
            
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.01)
            continue
            
        # 노트북의 빠른 CPU/GPU로 YOLO 연산 (TFLite 모델은 고정 해상도를 사용하므로 imgsz 제거)
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
