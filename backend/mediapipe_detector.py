"""
YOLO 대체용 MediaPipe 기반 detector.
기존 detector.py의 YOLO 클래스와 동일한 인터페이스(detect(frame) -> target 좌표)를
유지하도록 설계했습니다. main.py / state.py 쪽 호출부는 그대로 두고
이 클래스만 바꿔 끼우면 됩니다.
"""

import cv2
import mediapipe as mp


class MediaPipeDetector:
    def __init__(self, mode="hand", detection_confidence=0.6, tracking_confidence=0.5):
        """
        mode: "hand" 또는 "face"
        """
        self.mode = mode
        self.mp_hands = mp.solutions.hands
        self.mp_face = mp.solutions.face_detection

        if mode == "hand":
            self.model = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,  # 1개만 추적 -> 연산량 최소화, FPS 확보
                min_detection_confidence=detection_confidence,
                min_tracking_confidence=tracking_confidence,
            )
        else:
            self.model = self.mp_face.FaceDetection(
                model_selection=0,  # 0 = 2m 이내 근거리용 경량 모델 (웹캠 거리에 적합)
                min_detection_confidence=detection_confidence,
            )

    def detect(self, frame):
        """
        frame: BGR (OpenCV 기본 포맷)
        반환: (cx, cy) 픽셀 좌표 또는 못 찾으면 None
        기존 YOLO 클래스가 리턴하던 형식(예: bbox center)에 맞춰
        아래 return 부분만 조정하면 state.py 쪽 수정 없이 바로 연결됩니다.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False  # mediapipe 내부 최적화용
        h, w = frame.shape[:2]

        if self.mode == "hand":
            results = self.model.process(rgb)
            if results.multi_hand_landmarks:
                lm = results.multi_hand_landmarks[0].landmark[9]  # 중지 MCP = 손바닥 중심 근처
                cx, cy = int(lm.x * w), int(lm.y * h)
                return {
                    "cx": cx, "cy": cy,
                    "x": cx - 50, "y": cy - 50, "w": 100, "h": 100,
                    "conf": 1.0,
                    "predicted": False,
                    "detector": "mediapipe"
                }
            return None

        else:  # face
            results = self.model.process(rgb)
            if results.detections:
                box = results.detections[0].location_data.relative_bounding_box
                cx = int((box.xmin + box.width / 2) * w)
                cy = int((box.ymin + box.height / 2) * h)
                return {
                    "cx": cx, "cy": cy,
                    "x": cx - 50, "y": cy - 50, "w": 100, "h": 100,
                    "conf": 1.0,
                    "predicted": False,
                    "detector": "mediapipe"
                }
            return None

    def close(self):
        self.model.close()


if __name__ == "__main__":
    # 단독 테스트용 (라즈베리파이에 디스플레이 연결된 상태에서 FPS 확인용)
    import time

    cap = cv2.VideoCapture(0)
    det = MediaPipeDetector(mode="hand")
    prev = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        target = det.detect(frame)
        now = time.time()
        fps = 1 / (now - prev)
        prev = now

        if target:
            cv2.circle(frame, target, 8, (0, 255, 0), -1)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("MediaPipe Test", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    det.close()
