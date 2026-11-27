// 버전별 바뀐점 기록 (최신 버전이 맨 위)
// 새 버전을 추가할 때는 배열 맨 앞에 항목을 하나 추가하면 웹사이트 "바뀐점" 탭에 자동으로 나타납니다.
// 지난 버전 항목은 지우지 않습니다.

export const CURRENT_VERSION = 'v3.0.0';

export const CHANGELOG = [
  {
    version: 'v3.0.0',
    date: '2026-11-20',
    title: 'MediaPipe 손 제스처 추적 + 원격 관리 도구',
    summary:
      '마우스로 물체를 지정하던 방식에서, 손 제스처로 조종하는 손 추적 전용 실행기로 바꿨습니다. 주먹을 쥐면 따라가고, 손바닥을 펴면 멈춥니다.',
    added: [
      '손 추적 전용 실행기(hand_tracker.py): MediaPipe Hand Landmarker로 손 관절 21개를 인식',
      '제스처 판별: 주먹 = 따라가기, 손바닥 = 정지 (3프레임 연속일 때만 전환)',
      'Mac 원격 관리 도구 aivt: run · preview · calibrate · deps · clean · dashboard 를 한 줄 명령으로 실행',
      '자동 캘리브레이션: 모터를 조금 움직이고 화면이 밀린 양(px)을 측정해 °/px 게인 저장',
      '웹 미리보기(5001번 포트): 손 관절, 손바닥 중심, 추적 상태, fps 표시',
      '카메라 자동 밝기 조절: 노출 78~130, gain 0~40 범위에서 0.5초마다 조금씩 조정',
    ],
    changed: [
      '절대 각도 명령: "촬영 순간의 모터 위치 + 화면 오차"로 손의 각도를 구해 MOVE J XY 로 전송',
      '지연 보상 예측: 0.18초 앞을 예측해 겨냥 (최대 60px)',
      '모터 속도: 최대 3000 → 3500Hz, 가속도 15 → 25Hz/ms (탈조 없이 실측 확인)',
      'Raspberry Pi 4용 mediapipe 0.10.18 고정 (1.x 는 Pi 4 CPU 에서 실행되지 않음)',
    ],
    fixed: [
      '손을 놓칠 때 마지막 방향으로 "휙" 밀리던 문제: 새 검출이 있을 때만 명령 전송, 0.2초 놓치면 정지, 150px 넘게 튄 검출 무시, 명령 1회 이동량 제한',
      '빠르게 움직일 때 화면 번짐으로 손을 놓치던 문제: 카메라 노출 시간 단축 + 자동 밝기',
      '실행 중 ESP32 가 재시작되면 위치 기준이 바뀌므로 추적을 안전하게 정지',
      '라즈베리파이 SD카드 공간 확보 (남은 공간 678MB → 4.6GB)',
      'aivt dashboard 가 Flask 를 찾지 못하던 문제',
    ],
  },
  {
    version: 'v2.1.0',
    date: '2026-07-16',
    title: '폴더 구조 재조정 + MediaPipe 검출기 도입',
    summary: '프로젝트 폴더를 역할별로 다시 정리하고, 웹 대시보드의 YOLO 검출기를 MediaPipe 검출기로 바꿨습니다.',
    added: ['MediaPipe 검출기(mediapipe_detector.py): 손 또는 얼굴을 검출, 기존 YOLO 검출기와 같은 사용법 유지'],
    changed: [
      '폴더 구조를 backend / firmware / website / docs / archive 로 재조정',
      '웹 대시보드의 YOLO 검출기를 MediaPipe 검출기로 교체',
    ],
    fixed: [],
  },
  {
    version: 'v2.0.0',
    date: '2026-07-11',
    title: '패키지 구조 재정비 + 복귀 보장 리밋',
    summary: '코드를 역할별 패키지로 나누고, 리밋에 갇히지 않도록 안전 리밋 시스템을 다시 설계했습니다.',
    added: [
      '패키지 구조 재정비: config / core / hardware / web / data / scripts / tests',
      '복귀 보장 리밋: 리밋을 벗어나는 방향만 막고, 되돌아오는 방향은 절대 막지 않음',
      '작동 범위: M2(수직) ±45°, M1(수평) 360° — 카메라가 -25° 아래를 볼 때 자동 제한',
    ],
    changed: [
      '프론트엔드 2,716줄 script.js 를 17개 모듈로 분리',
      '자동 추적 중심 좌표를 실제 프레임 크기 기준으로 변경',
      '랜딩 페이지 개편: 다크 테마 3D 패널, 스펙 스트립, CAD 도면',
    ],
    fixed: [
      '사용자 리밋 병합의 부호 오류로 양방향이 모두 막히던 문제',
      '존재하지 않는 UI 요소 참조로 초기화가 중간에 멈추던 문제',
      '갤러리 삭제 API 의 경로 탐색(Path Traversal) 취약점',
    ],
  },
  {
    version: 'v1.5.0',
    date: '2026-07-06',
    title: '웹 프론트엔드 전면 개편',
    summary: '소개 웹사이트를 다크 모드와 3D 시뮬레이터 중심으로 새로 만들었습니다.',
    added: [
      '다크 모드 + Glassmorphism 테마',
      'Bento Box 레이아웃, Framer Motion 롤링 텍스트 랜딩 페이지',
    ],
    changed: ['React Three Fiber 3D 시뮬레이터 최적화 (컴포넌트 렌더링 분리로 프레임 드랍 해결)'],
    fixed: ['2축(Pan/Tilt) 추적 하드웨어 모니터링 환경 복구'],
  },
  {
    version: 'v1.4.0',
    date: '2026-07-03',
    title: '하드웨어 보호와 정밀 제어',
    summary: '실제 기기의 물리적 한계에 맞춰 모든 리밋 시스템을 다시 설계했습니다.',
    added: [
      '물리 각도 실측 적용: M1(수평) ±180°, M2(수직) +50° ~ -40°',
      '2D 충돌 방지 안전 구역: M2 가 -25° 아래로 내려가면 M1 회전 범위를 자동 축소',
      '자동 감속 제동: 리밋 도달 전부터 조이스틱 입력을 부드럽게 감속',
      '터미널(TUI) 실시간 리밋 경고, 웹 UI 전체화면 모드',
    ],
    changed: [],
    fixed: [],
  },
  {
    version: 'v1.3.0',
    date: '2026-07-03',
    title: '라즈베리파이 전용 환경',
    summary: '윈도우 없이 라즈베리파이 터미널에서 바로 실행되도록 만들었습니다.',
    added: [
      '라즈베리파이 독립 실행 패키지(raspi_main)',
      '자동화 스크립트 install.sh · start.sh · update.sh',
      'rich 기반 CLI 로딩 애니메이션, waitress 프로덕션 서버',
    ],
    changed: ['Linux(V4L2) 카메라에 MJPG 코덱 강제 지정 (1080p 30fps)'],
    fixed: ['중복 백업 파일과 압축 해제 잔여 폴더 정리'],
  },
  {
    version: 'v1.2.0',
    date: '2026-07-02',
    title: 'Apple 스타일 UI + 펌웨어 버전 검사',
    summary: '웹 대시보드를 플랫 디자인으로 바꾸고, 펌웨어 버전이 다르면 실행을 막도록 했습니다.',
    added: [
      'Apple Design System 기반 미니멀 플랫 UI',
      '펌웨어 버전 불일치 시 프로그램 즉시 종료 (기대 버전 2.0.7)',
    ],
    changed: [],
    fixed: ['조이스틱 끊김: HTTP 주기 20 → 80ms, ESP32 조그 Watchdog 150 → 350ms'],
  },
  {
    version: 'v1.1.0',
    date: '2026-06-30',
    title: '갤러리 삭제 + Arduino 폴백',
    summary: '미디어 갤러리 관리 기능과 Arduino 보드 지원 뼈대를 추가했습니다.',
    added: ['미디어 갤러리 이미지 개별 삭제', 'Arduino(Uno 등) 폴백 지원(motor_arduino.py)'],
    changed: ['모터 파라미터 탭 이름 정리, Set Home · E-STOP 버튼 위치 정리'],
    fixed: [],
  },
  {
    version: 'v1.0.0',
    date: '2026-06-29',
    title: '첫 릴리즈',
    summary: '드래그로 지정한 물체를 OpenCV 로 추적하는 첫 버전입니다.',
    added: [
      'AI 추적 코어: OpenCV CSRT Tracker + Competitive Tracking(전역 템플릿 매칭) + Kalman Filter',
      'ESP32 모터 제어 펌웨어: FreeRTOS 듀얼코어, 가감속 P 제어',
      'Glassmorphic 웹 UI: 반응형, 실시간 MJPEG 영상 스트리밍',
      '웹에서 모터 최대 속도 · 가속도 · steps/px 실시간 설정',
    ],
    changed: [],
    fixed: [],
  },
];
