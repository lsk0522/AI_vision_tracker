<div align="center">

<img src="docs/assets/turret_diagram.png" width="450" alt="AI Vision Tracker 터렛 CAD 도면" />

<br/>

<img src="https://img.shields.io/badge/MediaPipe-0097A7?style=for-the-badge&logo=google&logoColor=white"/>
<img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white"/>
<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/C++-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white"/>
<img src="https://img.shields.io/badge/Raspberry%20Pi-A22846?style=for-the-badge&logo=Raspberry%20Pi&logoColor=white"/>
<img src="https://img.shields.io/badge/ESP32-E7352C?style=for-the-badge&logo=espressif&logoColor=white"/>

<br/><br/>

# AI Vision Tracker `v3.0.0`

**손 제스처로 조종하는 2축 스텝모터 터렛**

✊ 주먹을 쥐면 손을 따라가고, ✋ 손바닥을 펴면 멈춥니다.

[🌐 웹사이트](https://lsk0522.github.io/AI_vision_tracker/) · [📝 바뀐점](./docs/CHANGELOG.md) · [📖 사용자 가이드](./docs/USER_GUIDE.md)

</div>

---

## 📋 한눈에 보기

하드웨어 : 라즈베리파이 4B, ESP32, 스텝모터 2개 (수평, 수직), DM542 드라이버 2개, 24V SMPS, 5V DC-DC 컨버터, USB 웹캠, 1:5 감속 기어 (16T → 80T)

소프트웨어 (라즈베리파이) : Python, MediaPipe, OpenCV, NumPy, pyserial, v4l2-ctl

소프트웨어 (ESP32) : C++ (Arduino), FreeRTOS, 가감속 제어

소프트웨어 (Mac 관리 도구) : Python, SSH

소프트웨어 (웹 대시보드) : Flask, HTML, CSS, JavaScript

통신 : UART 시리얼 (115200bps), USB, SSH, Wi-Fi

주요 기능 : 손 관절 인식, 제스처 판별 (주먹 = 따라가기, 손바닥 = 정지), 2축 자동 추적, 지연 보상 예측, 카메라 자동 밝기 조절, 자동 캘리브레이션, 조이스틱 수동 조작, 웹 미리보기

---

## 🏗️ 시스템 구성도

전원 : 24V SMPS → DM542 드라이버 2개 (모터 전원), 24V SMPS → 5V DC-DC 컨버터 → 라즈베리파이 4B

영상 : USB 웹캠 → (USB) → 라즈베리파이 4B

제어 : 라즈베리파이 4B → (USB 시리얼 115200bps) → ESP32 → (PUL / DIR / ENA) → DM542 드라이버 2개 → 스텝모터 2개 (수평, 수직)

관리 : Mac → (Wi-Fi, SSH) → 라즈베리파이 4B

화면 : 브라우저 → (Wi-Fi) → 라즈베리파이 4B (미리보기 5001번 포트, 대시보드 5000번 포트)

```text
                       ┌──────────────── 24V SMPS ────────────────┐
                       │                                          │
                       ▼                                          ▼
                5V DC-DC 컨버터                          DM542 드라이버 ×2
                       │                                    ▲          │
                       ▼                                    │          ▼
 USB 웹캠 ──USB──▶ 라즈베리파이 4B ──USB 시리얼──▶ ESP32 ──PUL/DIR/ENA──┘     스텝모터 ×2
                  (MediaPipe 손 인식,  115200bps  (FreeRTOS,                 (수평 Pan,
                   목표 각도 계산)                  가감속 펄스)               수직 Tilt)
                    ▲            ▲
          Wi-Fi·SSH │            │ Wi-Fi·HTTP
                    │            │
           Mac (aivt 관리 도구)   브라우저 (미리보기 · 대시보드)
```

```mermaid
graph LR
    CAM["📷 USB 웹캠<br/>640×480 · 30fps"] -->|USB| PI
    subgraph PI["🍓 라즈베리파이 4B"]
        MP["MediaPipe<br/>손 관절 21점"] --> GES["제스처 판별<br/>주먹 / 손바닥"]
        GES --> CTRL["목표 각도 계산<br/>+ 지연 보상 예측"]
    end
    CTRL -->|"USB 시리얼 115200bps<br/>MOVE J XY"| ESP["⚙️ ESP32<br/>FreeRTOS · 가감속"]
    ESP -->|PUL / DIR / ENA| DRV["DM542 ×2"]
    DRV --> M1["M1 수평 (Pan)"]
    DRV --> M2["M2 수직 (Tilt)"]
    MAC["💻 Mac · aivt"] -->|Wi-Fi · SSH| PI
    WEB["🌐 브라우저"] -->|"5001 미리보기<br/>5000 대시보드"| PI
    PSU["🔌 24V SMPS"] --> DRV
    PSU --> DCDC["5V DC-DC"] --> PI
```

---

## 🧠 동작 원리

```text
카메라 프레임 ──▶ MediaPipe 손바닥 중심 ──▶ "촬영 순간의 모터 위치 + 화면 오차" = 손의 절대 각도
                                                │
                                   지연 보상 예측 (0.18초 앞, 최대 60px)
                                                │
                                   MOVE J XY <M1> <M2>  (새 검출마다 1번) ──▶ ESP32
```

| 단계 | 하는 일 |
|:---|:---|
| **① 손 인식** | MediaPipe Hand Landmarker 가 손 관절 21개를 찾고, 손바닥 중심(관절 0·5·9·13·17 평균)을 구합니다 |
| **② 제스처 판별** | 주먹(FIST) = 따라가기, 손바닥(OPEN) = 정지. 3프레임 연속일 때만 바뀌고, 손이 1초 넘게 사라지면 정지합니다 |
| **③ 각도 계산** | 사진을 찍은 순간의 모터 위치에 화면 오차 × 게인(°/px)을 더해 손의 절대 각도를 구합니다. 같은 오차를 두 번 더하지 않습니다 |
| **④ 지연 보상** | 처리 지연만큼 손이 갈 곳을 예측해 조금 앞을 겨냥합니다 |
| **⑤ 안전 장치** | 손을 0.2초 놓치면 정지, 150px 넘게 튄 검출 무시, 명령 1번 이동량 제한, ESP32 가 재시작되면 추적 정지 |
| **⑥ 모터 구동** | ESP32 가 목표 각도까지 가감속 펄스를 만들고 DM542 가 스텝모터를 돌립니다 (최대 3500Hz, 가속도 25Hz/ms) |
| **⑦ 자동 밝기** | 0.5초마다 밝기를 재서 노출(78~130)과 gain(0~40)을 조절합니다. 번짐을 줄이려고 노출은 최대한 짧게 유지합니다 |

---

## 🚀 실행 방법

모든 명령은 **Mac 터미널**에서 실행합니다. `aivt` 가 SSH(`ssh pi`)로 라즈베리파이에 접속해 최신 코드를 올리고 실행합니다.

### 처음 한 번

```bash
aivt deps
```

```bash
aivt calibrate
```

- `aivt deps` : 라즈베리파이에 필요한 프로그램 설치 (Pi 4 는 mediapipe 0.10.18 자동 선택)
- `aivt calibrate` : 모터를 조금 움직여 화면이 몇 px 밀리는지 재고 게인을 저장합니다. 무늬가 있는 배경을 향하게 두세요.

### 손 추적

```bash
aivt run
```

```bash
aivt preview
```

- `aivt run` : 손 추적 시작. 끄려면 `Ctrl + C`
- `aivt preview` : 브라우저로 미리보기 (`http://<파이주소>:5001/`)
  - 주황 점 21개 = 손 관절, 초록 원 = 손바닥 중심, 흰 십자 = 화면 가운데

### 조이스틱 수동 조작 (웹 대시보드)

```bash
aivt dashboard
```

```bash
aivt web
```

- 브라우저에서 `http://<파이주소>:5000/` 의 조이스틱으로 조작합니다.
- 손 추적과 대시보드는 카메라와 ESP32 를 같이 쓰므로 **동시에 켤 수 없습니다.** 하나를 켜면 `aivt` 가 다른 하나를 자동으로 끕니다.

### 그 밖의 명령

| 명령 | 하는 일 |
|:---|:---|
| `aivt clean` | 라즈베리파이 공간 정리 (지우기 전에 목록을 보여 줌) |
| `aivt ssh` | 라즈베리파이 터미널 접속 |

---

## ⚙️ `aivt run` 옵션

옵션 없이 `aivt run` 만 쳐도 아래 기본값으로 실행됩니다. 바꾸고 싶은 값만 뒤에 붙이세요. 예: `aivt run --gain 0.9`

| 옵션 | 기본값 | 의미 |
|:---|:---:|:---|
| `--msl` | `3500` | ESP32 최대 속도 (Hz) |
| `--acc` | `250` | 가속도 (Hz/ms × 10, `250` = 25Hz/ms) |
| `--gain` | `1.0` | 모터 반응 배율. 지나쳤다 돌아오면 ↓, 느리면 ↑ |
| `--lead` | `0.18` | 지연 보상 예측 시간 (초) |
| `--max-lead-px` | `60` | 예측으로 앞서 보내는 최대량 (px) |
| `--lost-stop` | `0.2` | 손을 이 시간(초) 못 찾으면 정지 |
| `--jump-px` | `150` | 한 번에 이보다 크게 튄 검출은 무시 (px) |
| `--max-step` | 화면 200px 분량 | 명령 1번에 움직이는 최대 각도 (펌웨어 °) |
| `--deadzone` | `6` | 화면 가운데에서 이 범위(px) 안이면 움직이지 않음 |
| `--gesture` | `fist` | `any` 로 두면 제스처 없이 손만 보이면 따라감 |
| `--exposure` / `--cam-gain` | 자동 밝기 | 값을 주면 그 값으로 고정 (노출은 0.1ms 단위, 예: `130` = 13ms) |
| `--bright-target` | `120` | 자동 밝기 목표 (±20 안이면 그대로 둠) |
| `--ae-exp-max` / `--ae-gain-max` | `130` / `40` | 자동 밝기의 노출 · gain 상한 |
| `--proc-width` | `320` | MediaPipe 입력 폭. 작을수록 빠르지만 덜 정확 |
| `--preview-port` | `5001` | 미리보기 포트 (`0` = 끄기) |
| `--no-motor` | | 모터 없이 인식 · 미리보기만 |

**실측 튜닝 결과 (2026-11-20)** : 노출 130 / gain 30, 예측 0.18초 / 60px, 가속도 25Hz/ms 조합이 가장 부드러웠고 탈조가 없었습니다. `--lost-stop` 이나 `--jump-px` 를 늘리면 오히려 더 끊겼습니다.

---

## 🔧 하드웨어

| 부품 | 모델 / 사양 |
|:---|:---|
| 메인 컨트롤러 | Raspberry Pi 4 Model B |
| 모터 컨트롤러 | ESP32 (Lolin D32, FreeRTOS 듀얼코어) |
| 모터 드라이버 | DM542 × 2 |
| 모터 | 스텝모터 × 2 (M1 수평 Pan, M2 수직 Tilt) |
| 감속 기어 | 모터 16T → 출력 80T (1 : 5) |
| 전원 | 24V SMPS (모터), 5V DC-DC 컨버터 (라즈베리파이) |
| 카메라 | USB 웹캠 (640×480, 30fps, MJPG) |

### ESP32 ↔ DM542 배선 (펌웨어 `esp32_firmware.ino` 기준)

| 축 | ENA | DIR | PUL |
|:---|:---:|:---:|:---:|
| M1 (수평 Pan) | GPIO 13 | GPIO 14 | GPIO 16 |
| M2 (수직 Tilt) | GPIO 22 | GPIO 21 | GPIO 23 |

> 모터 드라이버 전원은 반드시 SMPS 를 쓰고, ESP32 전원으로 모터를 돌리지 마세요.

### 작동 범위 (안전 리밋)

- M1 (수평) : ±180°
- M2 (수직) : +50° ~ -40°
- 카메라가 -25° 아래를 볼 때는 기둥과 부딪히지 않도록 M1 범위가 자동으로 줄어듭니다.

### ESP32 펌웨어 (v2.0.7)

| 코어 | 태스크 | 하는 일 |
|:---:|:---:|:---|
| Core 0 | `serialTask` | 시리얼 명령 수신 (`MOVE J`, `S`, `CFG` 등) |
| Core 1 | `motorTask` | 가감속 계산 + DM542 펄스 출력 |

- 실행 중 설정 변경 : `CFG:MSL:<Hz>` (최대 속도), `CFG:ACC:<Hz/ms × 10>` (가속도)
- 5초 동안 명령이 없으면 모터 전류를 자동 해제합니다 (Watchdog).

---

## 📂 폴더 구조

```text
📦 AI_vision_tracker
 ┣ 📂 backend      라즈베리파이 코드 (hand_tracker.py 손 추적, main.py 웹 대시보드)
 ┣ 📂 firmware     ESP32 펌웨어 (esp32_firmware.ino)
 ┣ 📂 scripts      Mac 관리 도구 (aivt.py) 와 설치 · 실행 스크립트
 ┣ 📂 website      소개 웹사이트 (React + Three.js, GitHub Pages)
 ┣ 📂 hardware     터렛 3D 모델
 ┣ 📂 docs         문서 (CHANGELOG, USER_GUIDE, HANDOFF, 지난 버전 README)
 ┗ 📂 archive      지난 버전 코드 백업
```

---

## 📝 바뀐점

지난 버전 기록은 지우지 않고 남겨 둡니다. 웹사이트의 **바뀐점** 탭에서도 버전별로 볼 수 있습니다.

| 버전 | 날짜 | 핵심 내용 |
|:---|:---:|:---|
| **v3.0.0** | 2026-11-20 | MediaPipe 손 제스처 추적 전용 실행기, Mac 관리 도구 `aivt`, 지연 보상 예측, 카메라 자동 밝기 |
| v2.1.0 | 2026-07-16 | 폴더 구조 재조정, 웹 대시보드 YOLO → MediaPipe 검출기 교체 |
| v2.0.0 | 2026-07-11 | 패키지 구조 재정비, 복귀 보장 리밋 |
| v1.5.0 | 2026-07-06 | 웹 프론트엔드 전면 개편 (다크 모드, 3D 시뮬레이터) |
| v1.4.0 | 2026-07-03 | 물리 각도 실측, 충돌 방지 안전 구역, 자동 감속 제동 |
| v1.3.0 | 2026-07-03 | 라즈베리파이 전용 실행 환경 |
| v1.2.0 | 2026-07-02 | Apple 스타일 UI, 펌웨어 버전 검사 |
| v1.1.0 | 2026-06-30 | 갤러리 삭제, Arduino 폴백 |
| v1.0.0 | 2026-06-29 | 첫 릴리즈 (OpenCV CSRT 물체 추적) |

- 자세한 내용 : [docs/CHANGELOG.md](./docs/CHANGELOG.md)
- v2.1.0 까지의 README 원본 (CSRT · YOLO 물체 추적 버전) : [docs/versions/README_v2.1.0.md](./docs/versions/README_v2.1.0.md)

---

<div align="center">
  <p><i>본 프로젝트는 서울로봇고등학교 졸업작품의 일환으로 제작되었습니다.</i></p>
  <p>Made with ❤️ by <b>LSK0522</b></p>
</div>
