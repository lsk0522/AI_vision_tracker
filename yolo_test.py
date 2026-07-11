import cv2
import os
import time
from ultralytics import YOLO

# 1. 모델 경로 설정 (경로가 다를 경우 직접 수정해주세요)
MODEL_PATH = r"C:\Users\LSK0522\Downloads\best_int8.tflite"

if not os.path.exists(MODEL_PATH):
    print(f"❌ 오류: 모델 파일을 찾을 수 없습니다! 경로를 확인해주세요: {MODEL_PATH}")
    exit(1)

# 2. YOLOv8 모델 로드 (TFLite 모델)
print("🚀 YOLO TFLite 모델 로딩 중...")
model = YOLO(MODEL_PATH, task="detect")
print("✅ 모델 로딩 완료!")

# 3. 노트북 웹캠 열기 (Windows 최적화: DirectShow 사용 및 해상도 낮추기)
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

prev_time = 0

if not cap.isOpened():
    print("❌ 오류: 웹캠을 열 수 없습니다.")
    exit(1)

print("📷 웹캠 화면이 켜집니다. 종료하려면 화면이 선택된 상태에서 'q'를 누르세요.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ 프레임을 읽어올 수 없습니다.")
        break
        
    # 좌우 반전 (거울 모드 - 필요시 활성화)
    frame = cv2.flip(frame, 1)

    # 4. YOLO 객체 탐지 수행 (confidence를 0.25로 낮춰서 약간 달라도 억지로라도 찾게 만듦)
    results = model.predict(source=frame, conf=0.25, verbose=False)
    
    # 5. 유튜브 영상과 똑같이 bounding box 및 label, 확률(Confidence)을 이미지에 그려줌
    annotated_frame = results[0].plot()

    # FPS 계산 및 화면 표시 (얼마나 부드러운지 확인)
    curr_time = time.time()
    fps = 1 / (curr_time - prev_time) if prev_time > 0 else 0
    prev_time = curr_time
    cv2.putText(annotated_frame, f"FPS: {int(fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # 6. 화면에 결과 출력
    cv2.imshow("YOLOv8 Shuttlecock Tracking", annotated_frame)

    # 'q' 키를 누르면 종료
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 자원 해제
cap.release()
cv2.destroyAllWindows()
