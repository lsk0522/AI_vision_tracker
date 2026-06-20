<div align="center">
  <h1>🎯 AI Vision Tracker (Turret)</h1>
  <p><strong>스마트 객체 추적 시스템 및 웹 기반 터렛 컨트롤러</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
    <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" />
    <img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" />
    <img src="https://img.shields.io/badge/C++-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white" />
    <img src="https://img.shields.io/badge/ESP32-E7352C?style=for-the-badge&logo=espressif&logoColor=white" />
  </p>
  <p>고성능 객체 인식(CSRT) 알고리즘과 ESP32 스테퍼 모터 정밀 제어를 통해 움직이는 객체를 자동으로 추적하고 모니터링하는 AI 비전 트래커 프로젝트입니다.</p>
</div>

<br/>

## ✨ 주요 기능 및 특징 (Features)

### 🖥️ Apple 스타일 Glassmorphic Web UI & UX
- **다이내믹 인터페이스**: 모바일 친화적인 반응형 레이아웃 및 60fps 크로스헤어 애니메이션.
- **직관적인 조작**: 가상 조이스틱(수동 제어), 갤러리 뷰어, 실시간 설정 패널 지원.
- **상태 모니터링**: \LOCKED\, \SEARCHING\ 등 실시간 추적 상태 및 모터 연결 상태 시각화.

### 🤖 지능형 객체 추적 알고리즘 (AI Tracking)
- **CSRT 기반 객체 추적**: 드래그 한 번으로 대상을 지정하고 정밀하게 추적.
- **Competitive Tracking (경쟁적 복구 알고리즘)**: 화면을 벗어났거나 놓친 타겟을 전역 템플릿 매칭을 통해 스스로 다시 찾아내는 스마트 복구 로직.
- **다중 추적 지원**: 객체 추적 중 발생할 수 있는 노이즈를 대비한 피부색/배경 마스킹 기능 내장.

### ⚙️ 고성능 하드웨어 제어 (ESP32 & DM542)
- **부드러운 정밀 제어 (S-Curve & P-Control)**: 0 → 3000Hz 속도까지 8.0Hz/ms의 가속도로 부드럽고 강력하게 이동.
- **하드웨어 튜닝 완벽 호환**: 1:5 기어비 (모터 16T / 출력 80T) 등 다양한 물리적 환경에 대응.
- **실시간 파라미터 동기화**: 웹 UI에서 설정한 가속도, 최대 속도, 픽셀당 이동 거리가 즉각적으로 ESP32 컨트롤러의 타이머 인터럽트에 반영.
- **FOTA(Firmware Over-The-Air)**: 브라우저 상에서 버튼 클릭 한 번으로 ESP32 펌웨어 컴파일 및 업로드 가능 (arduino-cli 연동).

<br/>

## 🏗️ 시스템 아키텍처 (Architecture)

본 프로젝트는 백엔드(AI 연산/서버)와 펌웨어(모터 실시간 제어)가 역할을 분담하여 최상의 퍼포먼스를 발휘합니다.

\\\	ext
[ 웹 브라우저 (UI) ] <──(HTTP/API)──> [ Python Flask 서버 (Raspberry Pi/PC) ]
   - 수동 조작 (조이스틱)                - 영상 처리 및 AI 추적 (OpenCV/CSRT)
   - 모터 파라미터 설정                    - P-Control 좌표 연산
   - 실시간 비디오 스트리밍                - 비동기 시리얼 통신 브릿지
                                           │
                                       (Serial/USB)
                                           │
                                   [ ESP32 컨트롤러 ] <──(Pulse/Dir)──> [ DM542 모터 드라이버 ]
                                     - 하드웨어 타이머 제어                - NEMA 스텝 모터 구동
                                     - 정밀 가속도 제어 (accel)            - 1:5 기어비 터렛 물리계
\\\

<br/>

## 📂 프로젝트 파일 구조 (Directory Structure)

\\\	ext
📦 AI_vision_tracker
 ┣ 📂 esp32_firmware       # ESP32 C++ 펌웨어 (타이머 인터럽트 기반)
 ┣ 📂 static               # 프론트엔드 정적 파일 (script.js, style.css)
 ┣ 📂 templates            # 프론트엔드 HTML (index.html)
 ┣ 📂 learning_data        # 트래커 학습 타겟 데이터 저장소
 ┣ 📜 main.py              # Flask 서버 진입점 및 스레드 시작
 ┣ 📜 routes.py            # API 엔드포인트 라우팅 (설정, 모터 제어 등)
 ┣ 📜 detector.py          # OpenCV 객체 추적, 경쟁적 탐색 알고리즘
 ┣ 📜 camera.py            # 웹캠 비디오 스트림 캡처
 ┣ 📜 motor_esp32.py       # ESP32 비동기 시리얼 통신 (Thread-safe)
 ┣ 📜 serial_utils.py      # 포트 자동 감지 유틸리티
 ┗ 📜 state.py             # 전역 상태(State) 관리
\\\

<br/>

## 🚀 설치 및 실행 방법 (How to Run)

### 1. 요구 사항 (Prerequisites)
- **Python 3.11+**
- **Arduino CLI** (웹 UI를 통한 원격 펌웨어 업로드 사용 시)
- 연결된 웹캠 (USB/CSI)
- ESP32 개발 보드 및 스텝 모터 드라이버(DM542)

### 2. 의존성 설치
\\\ash
pip install flask opencv-python opencv-contrib-python numpy pyserial
\\\
*(이 프로젝트는 Pyright 기준 0 Error를 달성하여 완벽한 Type Hinting을 제공합니다.)*

### 3. 서버 실행
\\\ash
python main.py
\\\
터미널에 표시되는 로컬 IP 혹은 \http://localhost:5000\ 으로 접속합니다.

<br/>

## 🛠️ 트러블슈팅 및 튜닝 가이드

- **추적이 잘 풀리거나 버벅일 경우**: 
  웹 UI의 **'기기 설정'**에서 '조준점 반응 속도'를 줄이거나 대상 객체를 다시 학습시켜주세요.
- **모터의 속도가 너무 느리거나 빠른 경우**: 
  웹 UI의 **'모터 튜닝'** 탭에서 **최대 속도(Hz)** 및 **가속도(Hz/ms)** 를 조절하세요. 변경 사항은 즉시 ESP32에 반영됩니다. (권장 기본값: 3000Hz, 8.0Hz/ms)

<br/>

---
<div align="center">
  <p><i>본 프로젝트는 서울로봇고등학교 졸업작품의 일환으로 제작되었습니다.</i></p>
</div>
