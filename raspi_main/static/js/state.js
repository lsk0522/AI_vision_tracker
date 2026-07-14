/* ==========================================
   공유 상태 — 여러 모듈이 함께 읽고 쓰는 값들.
   ES 모듈은 import한 바인딩을 재대입할 수 없으므로
   (import된 let 변수에 값을 다시 넣을 수 없음), 하나의
   객체로 묶어서 모든 모듈이 state.xxx 형태로 읽고 쓴다.

   learningMode/learningProgress/currentLearnZone은 원래
   drawCrosshair()보다 먼저 선언되어야 한다는 제약이 있었는데
   (script.js 83번 줄 주석 참고), 이 파일이 다른 모든 모듈보다
   먼저 평가되는 첫 import 대상이므로 그 제약은 자동으로 지켜진다.
   ========================================== */
export const state = {
    // 조준점 렌더링 위치 / 목표 위치
    px: 320,
    py: 240,
    tPx: 320,
    tPy: 240,

    // 조이스틱 반응 속도 (1~20)
    maxSpeed: 5,

    // manual | auto
    controlMode: "manual",

    // 조이스틱 입력 상태
    joyVx: 0,
    joyVy: 0,
    joySendX: 0,
    joySendY: 0,
    joystickTouchId: null,
    _joySent: false,
    // seq를 0이 아닌 현재 시각(ms)에서 시작: 서버는 이전 세션의 마지막 seq보다 작은
    // 요청을 전부 STALE로 버리므로, 0부터 시작하면 새로고침 직후 조이스틱 명령이
    // 한동안 모두 무시되어 "딜레이/먹통"처럼 보인다. Date.now()는 항상 단조 증가.
    joySeq: Date.now(),

    // 위치 동기화 쓰로틀 타임스탬프
    lastSync: 0,

    // 학습 모드 상태
    learningMode: false,
    learningProgress: 0,
    currentLearnZone: { x: 170, y: 90, w: 300, h: 300 },

    // 자동 모드 야구공 검출 상태
    ballState: null,

    // pointer | joystick | auto
    inputMode: "joystick",

    // esp32 | arduino
    deviceType: "esp32",

    // ESP32 제어 모드: track | pos
    esp32Mode: "track",

    // Klipper 스타일 mm 위치 제어 현재 좌표 (퀵 SET HOME 버튼에서도 참조)
    klipperPosM1: 0.0,
    klipperPosM2: 0.0,
};
