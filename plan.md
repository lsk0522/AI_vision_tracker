# AI Vision Tracker 구현 설계 및 작업 계획서

## 1. 개요
이 문서는 AI Vision Tracker 시스템의 기능 고도화를 위한 설계도 및 진행 상황을 관리합니다. 현재 회원가입 및 모니터링 API 관련 작업이 완료되었으며, 이어서 비전 트래킹의 정밀도 향상을 위한 2축 초정밀 PID 추적 터렛 알고리즘의 설계 및 이식을 진행합니다.

---

## 2. 작업 관리 및 진행 상황

### 2.1 [Done] 회원가입 API 비밀번호 암호화(Hashing) 및 로그인 API 구현
*   **완료 시점**: 2026-07-16
*   **구현 내용**: `werkzeug.security` 라이브러리를 활용한 암호화 저장 및 `/login` API 구현, `test_auth.py`를 통한 검증 완료.

### 2.2 [Done] 과제 C: 안전 구역 경보 및 조준 오차 UI 피드백 API 구현
*   **완료 시점**: 2026-07-16
*   **구현 내용**: `/api/status/monitor` GET API 구현을 통해 안전 제한 작동 여부 및 조준 오차 제공 완료. `test_monitor.py` 테스트 검증 완료.

### 2.3 [Done] 폴더 구조 정리 및 비전 엔진 전면 교체 (YOLO ➔ MediaPipe)
*   **완료 시점**: 이전 리팩토링 단계 (Git Commit `b27c62b16`)
*   **구현 내용**: 
    *   `git mv`를 사용하여 `backend/`, `firmware/`, `website/` 등으로 깔끔하게 폴더 정리 완료.
    *   느린 YOLO 모델 대신 가볍고 실시간 처리가 가능한 `MediaPipe` 디텍터 모듈(`mediapipe_detector.py`)로 교체 완료 및 `detector.py`, `state.py` 연동 완료.

### 2.4 [Todo] 2축 초정밀 PID 추적 터렛 알고리즘 이식 및 리팩토링 (신규 추가)
*   **목표**: 타겟 추종 시의 오버슈트(Overshoot)와 잔진동을 획기적으로 억제하기 위해, 가상 조준점에 **PID(Proportional-Integral-Derivative) 제어 알고리즘**을 이식합니다.
*   **안전 규정**: 하드웨어 구동 모듈(`motor_esp32.py` 등)의 핵심 코드는 수정하지 않고, `routes/detector_routes.py` 내의 `/set_target` API에서 좌표를 스무딩하고 `state.point`로 전송하기 전에 가상 PID 필터를 적용하는 방식으로 연동합니다.

---

## 3. [PID 추적 알고리즘] 세부 설계 명세

### 3.1 PID 제어 수학적 모델 및 가상 필터 이식
*   **입력**: 검출 타겟 좌표 `tx`, `ty`
*   **가상 조준 위치**: `state._smooth_tx`, `state._smooth_ty`
*   **오차 계산**:
    *   $e_x(t) = tx - \text{state.\_smooth\_tx}$
    *   $e_y(t) = ty - \text{state.\_smooth\_ty}$
*   **PID 제어 수식**:
    *   **Proportional (비례)**: $P_x = K_p \times e_x(t)$
    *   **Integral (적분)**: $I_x = I_x + K_i \times e_x(t) \times dt$
        *   *적분 포화 방지(Anti-Windup)*: $I_x$의 최대치를 오차 누적으로 인한 발산 방지를 위해 특정 범위로 제한.
    *   **Derivative (미분)**: $D_x = K_d \times \frac{e_x(t) - e_x(t-1)}{dt}$
    *   **제어 출력**: $\text{output}_x = P_x + I_x + D_x$
*   **위치 업데이트**:
    *   $\text{state.\_smooth\_tx} \leftarrow \text{state.\_smooth\_tx} + \text{output}_x$
    *   $\text{state.\_smooth\_ty} \leftarrow \text{state.\_smooth\_ty} + \text{output}_y$
*   **PID 제어 파라미터 (기본값)**:
    *   $K_p = 0.15$ (부드럽게 타겟을 쫓아가는 비례 게인)
    *   $K_i = 0.01$ (누적 오차를 줄여 조준점에 딱 맞추는 적분 게인)
    *   $K_d = 0.05$ (급격한 추적이나 멈춤 시 댐핑을 가해 오버슈트를 잡는 미분 게인)

### 3.2 구현 계획 및 연동 위치
*   `backend/routes/detector_routes.py` 내의 `set_target()` API 수정:
    *   기존의 단순 1차 저주파 필터(`alpha = 0.12` 연산) 부분을 가상 PID 필터 알고리즘으로 대체.
    *   매 API 호출 사이의 시간 차이 `dt`를 계산하기 위해 `state.remote_tracking_last_time`과의 차이 사용 (0.001초 미만 방지 세이프가드 적용).
    *   오차 미분 연산을 위해 이전 오차값 `state._prev_err_x`, `state._prev_err_y` 및 누적 오차값 `state._integral_x`, `state._integral_y`를 `state` 객체에 동적으로 저장하여 유지.

### 3.3 테스트 검증 시나리오 (`tests/test_pid.py`)
*   신규 테스트 파일을 생성하여 가상 PID 필터가 시간에 따른 오차에 반응하여 정상적인 댐핑 및 제어 출력을 연산하는지 검증합니다.
    1. **안정 상태 검증**: 타겟 오차가 0일 때 제어 출력이 0이며 조준점 변화가 없는지 검증.
    2. **미분(D) 댐핑 동작 검증**: 타겟이 급격하게 정지했을 때 오차가 감소하면서 D항이 음수 제동 제어량을 발생시켜 조준 속도를 효과적으로 감속(오버슈트 억제)하는지 수치 검증.
    3. **적분(I) 누적 및 포화(Anti-Windup) 검증**: 미세 오차가 오랜 시간 지속될 때 누적 오차가 포화 임계치(Windup Limit)에 막혀 발산하지 않고 안전한 상태를 유지하는지 검증.
