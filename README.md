<div align="center">

<img src="docs/assets/turret_diagram.png" width="450" alt="Turret 3D Model" />

<br/>

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white"/>
<img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white"/>
<img src="https://img.shields.io/badge/C++-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white"/>
<img src="https://img.shields.io/badge/Raspberry%20Pi-A22846?style=for-the-badge&logo=Raspberry%20Pi&logoColor=white"/>
<img src="https://img.shields.io/badge/ESP32-E7352C?style=for-the-badge&logo=espressif&logoColor=white"/>

<br/><br/>

> 초경량 비전 엔진 **MediaPipe**와 2축 Pan-Tilt 스테퍼 모터 **초정밀 PID 제어**를 결합하여  
> 움직이는 타겟을 미끄러지듯 부드럽게 자동 추적하고 모니터링하는 스마트 AI 비전 트래커 프로젝트입니다.
> 
> **🏆 v2.1.0+ 업데이트 내역:**
> - **초경량 비전 트래커 탑재**: 무거운 YOLO 모델을 대체하여 라즈베리파이의 연산 자원을 최소화하는 실시간 MediaPipe 디텍터 이식 완료.
> - **2축 가상 PID 제어기**: 타겟 추종 시의 오버슈트(Overshoot)와 잔진동을 획기적으로 억제하는 Proportional-Integral-Derivative 제어 이식.
> - **Anti-Windup 탑재**: I 제어기 오차 누적으로 인한 모터 제어 신호 발산을 원천 차단하는 포화 제한 장치 추가.
> - **인증 보안 강화**: 이메일 중복 검증 및 비밀번호 단방향 PBKDF2 해싱 암호화 저장, 안전한 로그인 API 구현.
> - **실시간 안전 상태 모니터링**: 모터 소프트웨어 리밋 제한 상황 및 비전 조준 오차(Pixel Error) 피드백 제공 API 추가.
> - **통합 단위 테스트 구축**: API 및 알고리즘 검증을 위한 12개 시나리오 테스트 전원 통과 확인.
<br/>

**👉 [📖 초보자를 위한 상세 사용자 가이드 (USER GUIDE) 보러 가기](./docs/USER_GUIDE.md)**

<br/>

</div>

---

## ✨ 주요 기능 및 특징 (Features)

### 🖥️ Apple 스타일 미니멀리즘 플랫 UI & 대시보드
- **Apple Design System**: 미니멀한 테마와 Glassmorphism 디자인 적용.
- **실시간 모니터링**: 타겟과의 조준 오차 및 모터 실시간 안전 제한 상황을 실시간 시각화.
- **⎋ 전역 세션 탈출**: 작동 이상 시 언제든 ESC 키로 안전 복귀 및 모터 즉시 멈춤 지원.

### 🤖 지능형 객체 추적 알고리즘 (AI Tracking & PID Control)
- **MediaPipe 기반 객체 추적**: 라즈베리파이 CPU에 부하를 주지 않는 초경량 손(Hand)/얼굴(Face) 추적 기능 기본 지원.
- **2축 가상 PID 추적 필터**: 가상 조준점에 미분(D) 감속 댐핑과 적분(I) 누적 오차 보정을 가해 미끄러지듯 부드러운 하드웨어 회전을 연출.
- **Anti-Windup 제어**: 미세 오차 지속 시의 누적 오차 한계를 제한하여 하드웨어 폭주를 방지.

### ⚙️ 고성능 하드웨어 제어 (ESP32 & DM542)
- **부드러운 정밀 제어 (S-Curve & P-Control)**: 0 → 3000Hz 속도까지 부드럽고 강력하게 가속도 제어.
- **실시간 소프트웨어 리밋**: 물리적 한계점(Pan ±180°, Tilt -45°~+50°)에 도달하거나 충돌 위험이 있을 경우 자동으로 제어량을 가로채 구동을 차단.
- **FOTA(Firmware Over-The-Air)**: 브라우저 상에서 버튼 클릭 한 번으로 ESP32 펌웨어 무선 업로드 지원.

---

## 🏗️ 시스템 아키텍처 (Architecture)

본 프로젝트는 백엔드(AI 연산/서버)와 펌웨어(모터 실시간 제어)가 역할을 분담하여 최상의 퍼포먼스를 발휘합니다.

```text
[ 웹 브라우저 (UI) ] <──(HTTP/API)──> [ Python Flask 서버 (Raspberry Pi/PC) ]
   - 수동 조작 (조이스틱)                - 영상 처리 및 AI 추적 (OpenCV/MediaPipe)
   - 모터 파라미터 설정                    - 가상 PID 및 오차 연산 (dt 기반)
   - 실시간 비디오 스트리밍                - 비동기 시리얼 통신 브릿지
                                           │
                                       (Serial/UART)
                                           │
                                   [ ESP32 컨트롤러 ] <──(Pulse/Dir)──> [ DM542 모터 드라이버 ]
                                     - 하드웨어 타이머 제어                - NEMA 스텝 모터 구동
                                     - 정밀 가속도 제어 (accel)            - 1:5 기어비 터렛 물리계
```

---

## 🛡️ 하드웨어 보호 및 개발 수칙 (Critical Safety Rules)

> [!IMPORTANT]
> **모터 제어 핵심 로직 보호 수칙**
> - 하드웨어 모터 직접 구동 및 저레벨 시리얼 전송을 전담하는 **[motor_esp32.py](file:///C:/Users/LSK0522/OneDrive%20-%20%EC%84%9C%EC%9A%B8%EB%A1%9C%EB%B4%87%EA%B3%A0%EB%93%B1%ED%95%99%EA%B5%90/%EB%B0%94%ED%83%95%20%ED%99%94%EB%A9%B4/%EC%A1%B8%EC%97%85%EC%9E%91%ED%92%88/Softwere/AI_vision_tracker-main%20v1.0.0/AI_vision_tracker-main/backend/motor_esp32.py) 코드는 안전 사고 방지를 위해 절대 직접 수정하지 마십시오.**
> - 모터의 감속이나 스무딩이 필요할 경우, 제어 입력을 직접 수정하지 않고 가상 조준 좌표 단계(`routes/detector_routes.py` 의 `set_target`)에서 소프트웨어 PID 필터를 활용하여 데이터를 가공해 주입하는 방식을 취해야 합니다.

---

## 🔌 신규 추가 API 명세서 (API Specification)

### 1. 모터 상태 및 조준 오차 모니터링 API
*   **Endpoint**: `GET /api/status/monitor`
*   **Content-Type**: `application/json`
*   **Response (200 OK)**:
    ```json
    {
      "limit_active": true,
      "limit_message": "M2 upper limit reached! (-6.50 deg)",
      "target_error_x": 15,
      "target_error_y": -40,
      "current_point": [335, 200]
    }
    ```

### 2. 회원가입 API
*   **Endpoint**: `POST /signup`
*   **Request Body**:
    ```json
    {
      "email": "user@example.com",
      "password": "Password123!"
    }
    ```
*   **Response (201 Created)**: `"message": "회원가입이 완료되었습니다."` (비밀번호는 안전하게 PBKDF2 단방향 해싱되어 저장됩니다.)

### 3. 로그인 API
*   **Endpoint**: `POST /login`
*   **Request Body**:
    ```json
    {
      "email": "user@example.com",
      "password": "Password123!"
    }
    ```
*   **Response (200 OK)**: `"message": "로그인에 성공했습니다."` (인증 실패 시 보안 유지를 위해 동일한 `401 Unauthorized` 오류 메시지를 반환합니다.)

---

## 📂 프로젝트 파일 구조 (Directory Structure)

```text
📦 AI_vision_tracker
 ┣ 📂 backend              # AI 연산, 가상 PID 및 웹 서버 로직 모듈
 ┃ ┣ 📂 routes             # API 엔드포인트 라우팅 (비전 제어, 모터 관리, 인증)
 ┃ ┣ 📜 state.py           # 시스템 전역 상태 및 파라미터 변수 정의
 ┃ ┣ 📜 detector.py        # 로컬 MediaPipe 비전 탐지 코어 루프
 ┃ ┗ 📜 camera.py          # 카메라 프레임 수집 및 MJPEG 스트림 처리
 ┣ 📂 firmware             # ESP32 C++ FreeRTOS 듀얼코어 모터 제어 펌웨어
 ┣ 📂 website              # React 기반 3D 시뮬레이션 웹 대시보드
 ┣ 📂 hardware             # 2축 터렛 3D CAD 모델링 및 기어 설계
 ┣ 📂 docs                 # 사용자 가이드, Changelog 등 기술 문서
 ┣ 📂 raspi_main           # 라즈베리파이 실기 배포용 독립 실행 사본
 ┣ 📂 tests                # 테스트 검증 폴더 (인증, 모니터링, PID 시뮬레이션)
 ┣ 📜 main.py              # Flask 서버 실행 및 백그라운드 태스크 기동 진입점
 ┗ 📜 plan.md              # 프로젝트 개발 마일스톤 및 세부 명세서
```

---

## 🚀 실행 및 테스트 검증 방법 (How to Test)

### 1. 요구 사항 및 설치
- **Python 3.11+** 및 관련 패키지 설치:
  ```bash
  pip install flask opencv-python opencv-contrib-python numpy pyserial mediapipe
  ```

### 2. 백엔드 기동
```bash
python main.py
```

### 3. 단위 테스트 일괄 검증 (All Green)
개발된 모든 기능의 안정성 검증을 위해 `tests` 디렉토리 아래의 테스트 시나리오를 구동합니다:
```bash
# 1. 회원가입 및 비밀번호 암호화 해싱, 로그인 로직 검증 (9개 시나리오)
python tests/test_auth.py

# 2. 실시간 안전 제한 경보 및 편차 변환 모니터링 API 검증 (3개 시나리오)
python tests/test_monitor.py

# 3. 2축 가상 PID 및 Anti-Windup 댐핑 동작 시뮬레이션 검증 (3개 시나리오)
python tests/test_pid.py
```
*(모든 테스트가 성공적으로 동작하면 콘솔에 `OK` 문구가 출력됩니다.)*

---

<div align="center">
  <p><i>본 프로젝트는 서울로봇고등학교 졸업작품의 일환으로 제작되었습니다.</i></p>
  <p>Made with ❤️ by <b>LSK0522</b></p>
</div>
