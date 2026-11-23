# CLAUDE.md — AI Vision Tracker

Claude Code 가 이 저장소에서 작업할 때 먼저 읽는 파일입니다. 현재 진행 상황·다음 할 일은 **`docs/HANDOFF.md`** 에 있습니다.

## 프로젝트 한 줄 요약
2축(Pan=M1 / Tilt=M2) 스텝모터 터렛 + 카메라. 라즈베리파이가 카메라 영상을 처리하고 ESP32(펌웨어 v2.0.7)가 DM542 드라이버로 모터를 구동합니다.
현재 목표: **MediaPipe 로 사람 손을 인식해서 ✊ 주먹이면 따라가고 ✋ 손바닥이면 정지.**

## 사용자 / 대화 규칙
- 사용자는 한국어로 대화합니다. 설명은 쉽게, **명령어는 한 줄씩, 주석 없이** 주세요.
  (Mac zsh 는 터미널에 직접 친 줄의 `# 주석` 을 처리하지 않아서 `unknown file attribute` 에러가 납니다.)
- 명령을 줄 때는 **Mac 에서 칠 것인지, 파이에서 칠 것인지** 분명히 구분하세요. 파이 쪽은 가능하면 `aivt ...` 또는 `ssh pi '...'` 형태로 Mac 에서 실행하게 합니다.
- 기존 코드(웹 대시보드 `backend/main.py` 계열, 펌웨어)는 **사용자가 요청하지 않으면 수정하지 않습니다.** 손 추적은 별도 파일(`backend/hand_tracker.py`)로 진행 중입니다.
- 지우기·덮어쓰기처럼 되돌리기 어려운 작업은 먼저 묻고, 백업 경로를 남기세요.

## 환경
| 항목 | 값 |
|:---|:---|
| Mac | Intel MacBook Pro, 이 폴더 `~/Desktop/AI_vision_tracker-main` 이 **기준(source of truth)** |
| Mac 폴더 | GitHub 에서 **ZIP 으로 받은 것 — git 저장소 아님** (`lsk0522/AI_vision_tracker`) |
| 파이 | **Raspberry Pi 4** (CPU 에 AES 없음 → mediapipe **0.10.18 고정**, 1.x 는 실행 시 죽음), 호스트명 `AIVisionTraker`, 사용자 `pi30306`, 64bit aarch64, Python 3.11, SD 15GB (2026-11-19 정리 후 약 3.7GB 남음) |
| 파이 접속 | `ssh pi` (IP 가 자주 바뀜 → `~/.ssh/config` 의 ProxyCommand 가 `scripts/find_pi.py` 로 자동 탐색) |
| 파이 코드 위치 | `/home/pi30306/AI_vision_tracker` — 원래 **옛 평면 구조**(최상위에 main.py 등). 그 안에 Mac 과 같은 `backend/ scripts/ firmware/` 가 aivt 로 새로 생김 |
| 파이 가상환경 | 옛 대시보드: `~/AI_vision_tracker/.venv` / 손 추적 전용: `~/AI_vision_tracker/backend/.venv` (분리 — main.py 환경을 건드리지 않기 위해) |

⚠ Mac 의 바탕화면은 iCloud "데스크탑 및 문서" 동기화 때문에 파일이 휴지통으로 가거나 **이전 버전으로 되돌아간 적이 있습니다.** 파일을 고친 뒤에는 실제로 반영됐는지(크기/내용) 확인하세요.

## 폴더 구조 (중요한 것만)
```
backend/                 파이에서 실행되는 코드
  main.py                기존 Flask 웹 대시보드 (port 5000) — 수정 금지(요청 시만)
  motor_esp32.py         ESP32 시리얼 (연결·재연결·POS 피드백). hand_tracker 가 import 해서 그대로 사용
  state.py               전역 상태 (모터 파라미터, 펌웨어 버전 2.0.7 기대)
  detector.py / mediapipe_detector.py / routes/   기존 파이프라인
  hand_tracker.py        ★ 손 추적 단독 실행기 (새로 만든 것)
  hand_tracker_run.sh    파이에서 직접 실행할 때 도우미
  hand_landmarker.task   MediaPipe Tasks API 손 모델 (7.8MB)
  remote_tracker.py      노트북에서 YOLO(셔틀콕) 돌려 /set_target 으로 보내는 옛 방식
firmware/esp32_firmware/esp32_firmware.ino   v2.0.7
scripts/
  aivt.py                ★ Mac 관리 도구 (동기화·실행·정리·되돌리기)
  aivt_remote.py         aivt 가 파이의 ~/.aivt/remote.py 로 자동 설치하는 도우미
  find_pi.py             IP 바뀌어도 파이 찾기 (캐시 → mDNS → /24 스캔, SSH 호스트키로 확인)
  setup_ssh_key.sh / install_ssh_alias.sh    SSH 키 + `ssh pi` 별칭
  run_laptop_tracker.sh  remote_tracker.py 실행 (Mac)
tools/sim/sim.py         ★ 하드웨어 없이 검증하는 시뮬레이터 (가짜 ESP32 pty + 가짜 카메라)
raspi_main/ website/ hardware/ archive/   옛 사본·웹사이트·3D 모델 (파이에선 불필요)
```

## 하드웨어 / 펌웨어 계약 (코드 읽고 확인한 사실)
- 시리얼 115200. 펌웨어 명령: `T:x:y`(화면좌표 상대 추적), `MOVE J XY a1 a2`(절대 각도), `S`(즉시 정지), `REL`/`ENA`, `CFG:KEY:VAL`, `POS`.
- 피드백 `POS:m1*100:m2*100:spd1:spd2` 를 30ms 마다 보냄. 단위는 **펌웨어 각도(°) = steps / 44.44**. 물리 각도와 다를 수 있음 (`state.py` 주석: 물리 180° = 펌웨어 22.7).
- 펌웨어 리밋(`setTargetAngles`): M2 ±45, M2 가 −45~−25 이면 M1 ±85, 그 외 M1 ±180 — **펌웨어 단위라 물리 한계보다 훨씬 넓음. 이것만 믿으면 안 됨.**
- ⚠ **물리 안전 한계** (`.agents/rules/hardware-safety.md`, `routes/core.py` 조이스틱 로직과 동일): M1 ±180°, M2 위 +50° / 아래 −40°, 카메라가 −25° 아래면 M1 ±80°, M1 이 ±80° 넘으면 M2 −25° 까지. 변환은 `state.py` (M1: 물리 180° = 펌웨어 22.7 / M2: 위 +50° = −6.5, 아래 −40° = +4.0, **펌웨어 음수 = 위**).
- 기존 에이전트 규칙 `.agents/AGENTS.md`, `.agents/rules/*.md` 도 지킬 것 (하드웨어 안전, 추적 복잡도 낮게).
- 속도 프로파일: 목표속도 = min(MSL 3000Hz, 남은스텝×8), 동적 가속. 5초 명령 없으면 홀딩 전류 해제.
- `T:x:y` 는 *명령 받은 순간 위치 + (px−320)×3.5 스텝* → 지연이 있으면 오차를 두 번 더해 오버슈트.
- 참고(미수정): `motor_esp32.py` 의 파이썬 M2 소프트 리밋은 펌웨어 계산과 **부호가 반대로 보임**. 실제로는 펌웨어 리밋만 동작.

## hand_tracker.py 설계
- 카메라 최신 프레임 + 촬영 시각 → MediaPipe(구버전 `mp.solutions` / 신버전 Tasks API 자동 선택; mediapipe ≥0.10.3x·1.x 는 solutions 삭제됨)
- 손바닥 중심 = 랜드마크 0,5,9,13,17 평균. 제스처: 검지~새끼 끝마디/둘째마디의 손목 거리비 → `FIST`/`OPEN`/`OTHER`, 3프레임 연속일 때 전환 (`GestureGate`, 시작=STOP, 손 1초 사라지면 STOP)
- 제어: **절대 목표 = 촬영 순간 모터 위치(PoseHistory 보간) + k × 화면오차(px, 640 기준)** → 축별 알파-베타 필터 → `lead` 초 앞 예측 → **`SafetyLimits.clamp`(물리 안전 한계 + 사용자 soft_limit, 여유 2°)** → 50Hz 로 `MOVE J XY` (변화 0.02° 이상일 때만). 정지는 제어 스레드에서 `S`. 캘리브레이션 이동도 같은 리밋 적용.
- 게인 k(°/px): `--calibrate` 가 모터를 ±1° 움직이며 위상상관으로 측정 → `backend/hand_tracker_calib.json`. 없으면 펌웨어 환산 3.5/44.44.
- 모터는 `motor_esp32.start()` 를 그대로 쓰고 `state.control_mode="manual"` 로 둬서 기존 루프가 T 를 안 보내게 함. `OK MOVE` 응답 로그는 `_parse_status` 를 감싸서 숨김(파일 수정 없음).
- `main.py` 와 카메라·시리얼을 공유할 수 없음 → 동시에 실행 금지 (aivt 가 자동 정지).

## aivt (Mac) 동작
- `aivt sync`: 동기화 대상 `backend/ scripts/ firmware/` (제외: `__pycache__ .venv picture learning_data hand_tracker_calib.json` 등). sha256 매니페스트 비교 → 바뀐 파일만 tar 로 전송. 파이 쪽에서 마지막 동기화 이후 바뀐 파일은 **충돌로 묻기**(y/s/d/n). 덮어쓴 파일은 파이 `~/.aivt/backups/` (10개). 파이에만 있는 파일은 지우지 않음.
- `aivt run|calibrate|dashboard`: 자동 sync → `ssh -t pi python3 ~/.aivt/remote.py launch ...`
- `aivt deps`: 64bit 확인 → 공간 확인(≥1.2GB) → `backend/.venv` 에 `mediapipe pyserial` (`--no-cache-dir`, 이어받기 재시도). 실패하면 Mac 에서 aarch64/cp311 휠을 받아 전송 후 `--no-index` 설치.
- `aivt clean`: 파이 공간 분석 → 번호 선택 삭제. 캐시는 바로, 코드/데이터는 **Mac `~/AIVT_pi_backup/` 으로 tar 백업 후** 삭제, apt/journal/불필요 패키지는 `ssh -t` + sudo. 홈 밖 경로 삭제 거부.
- 설정: Mac `~/.config/ai_vision_tracker/aivt.json`(파이 루트), `pi.json`(find_pi 캐시·호스트키).
- 내부 ssh 호출은 반드시 `stdin=DEVNULL` (안 그러면 사용자가 칠 답을 ssh 가 먹음 — 실제로 겪은 버그).

## 검증 방법 (하드웨어 없이)
- `python3 tools/sim/sim.py new --traj step|sine|fast|gesture` / `old ...` / `calib --ratio 0.156`
  pyserial·opencv·numpy 필요. pty 로 가짜 ESP32 를 띄우고 실제 `motor_esp32.py` 를 연결합니다.
- 시뮬레이션 결과(게인 일치): 기존 방식 스텝 응답 진동·정착 실패 / 새 방식 0.6s 정착, sine 오차 48→24px. 게인 6.4배 틀리면 캘리브레이션 없이는 둘 다 실패.
- MediaPipe 판별 테스트 이미지: `https://storage.googleapis.com/mediapipe-assets/{fist,thumb_up,pointing_up,victory,right_hands,left_hands}.jpg`
- aivt 는 로컬 sshd 를 "가짜 파이"로 띄워 `Host pi` 를 127.0.0.x 로 향하게 해서 테스트했습니다.
