"""
핵심 라우트 — index, video, click, pos, capture, flip, settings, set_speed,
             joystick_dir, set_input_mode, set_device_type, reconnect, available_ports
"""
from flask import Blueprint, Response, request, jsonify, render_template
import state

bp = Blueprint('core', __name__)


@bp.route('/')
def index():
    return render_template("index.html")


@bp.route('/video')
def video():
    from camera import gen_frames
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@bp.route('/click')
def click():
    try:
        x = int(float(request.args.get('x', 320)))
        y = int(float(request.args.get('y', 240)))
    except (TypeError, ValueError):
        return "INVALID", 400
    state.point = [x, y]
    state.last_point = (x, y)
    if state.esp32_control_mode != "track":
        import motor_esp32 as esp
        esp.set_mode("track")
    return "OK"


@bp.route('/pos')
def pos():
    return jsonify(x=state.point[0], y=state.point[1])


@bp.route('/capture')
def capture():
    from capture import save_capture
    save_capture()
    return "OK"


@bp.route('/flip')
def flip():
    state.flip_enabled = not state.flip_enabled
    return "OK"


@bp.route('/settings')
def settings():
    return jsonify(
        speed=state.speed,
        control_mode=state.control_mode,
        tracking_mode=state.tracking_mode,
        device_type=state.device_type,
        input_mode=state.input_mode,
    )


@bp.route('/set_speed')
def set_speed():
    try:
        speed = int(request.args.get("speed", state.speed))
    except (TypeError, ValueError):
        return "INVALID", 400
    state.speed = speed
    _sync_speed_to_esp32(speed)
    return "OK"


def _sync_speed_to_esp32(speed: int):
    """speed 1~20 값을 ESP32 MSL로 즉시 동기화."""
    hz = speed * 150   # 1=150Hz(매우 느림) ~ 20=3000Hz(빠름)
    state.esp32_max_speed_hz = hz
    if state.device_type == "esp32" and state.motor_connected:
        import motor_esp32 as esp
        esp.send_config("MSL", hz)



@bp.route('/joystick_dir')
def joystick_dir():
    # 미세조정을 위해 float로 받음 (script.js에서 -1.0 ~ 1.0 전송)
    x = float(request.args.get('x', 0))
    y = float(request.args.get('y', 0))

    import motor_esp32 as esp
    
    # 조이스틱을 건드리면 즉시 수동(manual) 모드로 전환하여 무거운 AI(YOLO) 연산을 중지시킵니다.
    if state.control_mode != "manual":
        state.control_mode = "manual"
        state.input_mode = "joystick"
    
    if state.esp32_control_mode != "pos":
        esp.set_mode("pos")
            
    if abs(x) < 0.001 and abs(y) < 0.001:
        # 조이스틱에서 손을 뗌 → 즉시 정지
        esp.stop_motors()
    else:


        # --- 파이썬 소프트웨어 리밋 (다이나믹 2D 안전 영역 + 자동 감속) ---
        m1_e = state.esp32_pos_m1_deg
        m2_e = state.esp32_pos_m2_deg
        
        m1_p = state.get_m1_phys()
        m2_p = state.get_m2_phys()

        block_y_pos = False; block_y_neg = False
        block_x_pos = False; block_x_neg = False
        limit_reason = ""

        # 1. 2D 다이나믹 하드웨어 한계 계산 (물리 각도)
        hw_m2_max = 50.0
        hw_m2_min = -25.0 if (m1_p > 80.0 or m1_p < -80.0) else -40.0
        
        hw_m1_max = 80.0 if (m2_p < -25.0) else 180.0
        hw_m1_min = -80.0 if (m2_p < -25.0) else -180.0

        # 2. 사용자 설정 리밋을 물리 각도로 변환하여 하드웨어 한계와 병합 (더 타이트한 값 적용)
        eff_m1_max = hw_m1_max
        eff_m1_min = hw_m1_min
        if state.soft_limit_m1_max is not None:
            usr_m1_max = state.soft_limit_m1_max / getattr(state, '_M1_PHYS_TO_ESP32', 0.1261)
            eff_m1_max = min(eff_m1_max, usr_m1_max)
        if state.soft_limit_m1_min is not None:
            usr_m1_min = state.soft_limit_m1_min / getattr(state, '_M1_PHYS_TO_ESP32', 0.1261)
            eff_m1_min = max(eff_m1_min, usr_m1_min)

        eff_m2_max = hw_m2_max
        eff_m2_min = hw_m2_min
        # M2 ESP32값과 물리각도는 부호가 반대일 수 있으므로(위가 -ESP32, 아래가 +ESP32) 주의
        # 사용자가 설정한 soft_limit_m2_min (ESP32 -6.5, 물리 50) -> 위쪽(max)
        # 사용자가 설정한 soft_limit_m2_max (ESP32 +4.0, 물리 -40) -> 아래쪽(min)
        if state.soft_limit_m2_min is not None:
            # ESP32 음수 -> 물리 양수 (UP)
            up_p = getattr(state, '_M2_PHYS_AT_UP', 50.0)
            up_e = abs(getattr(state, '_M2_ESP32_AT_UP', -6.5))
            usr_m2_max = -(state.soft_limit_m2_min) * (up_p / up_e) if state.soft_limit_m2_min < 0 else 0
            eff_m2_max = min(eff_m2_max, usr_m2_max)
        if state.soft_limit_m2_max is not None:
            # ESP32 양수 -> 물리 음수 (DOWN)
            dn_p = getattr(state, '_M2_PHYS_AT_DOWN', 40.0)
            dn_e = abs(getattr(state, '_M2_ESP32_AT_DOWN', 4.0))
            usr_m2_min = -(state.soft_limit_m2_max) * (dn_p / dn_e) if state.soft_limit_m2_max > 0 else 0
            eff_m2_min = max(eff_m2_min, usr_m2_min)

        # 3. 브레이킹 거리 설정 (이 거리 안으로 들어가면 속도가 점점 줄어듦)
        brake_dist_m1 = 20.0
        brake_dist_m2 = 15.0
        max_speed = 5.0  # 조이스틱 최대 입력값 추정치

        # M2 (수직) 자동 감속 및 차단
        if y > 0: # 아래로 이동 중 (min 방향)
            dist = m2_p - eff_m2_min
            if dist <= 0:
                y = 0.0; block_y_pos = True
                limit_reason = f"[M2 DOWN] Limit Reached ({eff_m2_min:.0f}°)"
            elif dist < brake_dist_m2:
                y = min(y, (dist / brake_dist_m2) * max_speed)
        elif y < 0: # 위로 이동 중 (max 방향)
            dist = eff_m2_max - m2_p
            if dist <= 0:
                y = 0.0; block_y_neg = True
                limit_reason = f"[M2 UP] Limit Reached ({eff_m2_max:.0f}°)"
            elif dist < brake_dist_m2:
                y = max(y, -(dist / brake_dist_m2) * max_speed)

        # M1 (수평) 자동 감속 및 차단
        if x > 0: # 우측으로 이동 중 (max 방향)
            dist = eff_m1_max - m1_p
            if dist <= 0:
                x = 0.0; block_x_pos = True
                limit_reason = f"[M1 RIGHT] Limit Reached ({eff_m1_max:.0f}°)"
            elif dist < brake_dist_m1:
                x = min(x, (dist / brake_dist_m1) * max_speed)
        elif x < 0: # 좌측으로 이동 중 (min 방향)
            dist = m1_p - eff_m1_min
            if dist <= 0:
                x = 0.0; block_x_neg = True
                limit_reason = f"[M1 LEFT] Limit Reached ({eff_m1_min:.0f}°)"
            elif dist < brake_dist_m1:
                x = max(x, -(dist / brake_dist_m1) * max_speed)

        state.active_limit_msg = limit_reason
        # -----------------------------------------------------------------

        if abs(x) < 0.001 and abs(y) < 0.001:
            esp.stop_motors()
        else:
            # 순수 조그(Velocity) 제어 방식: 목표 위치를 보내는 대신 "속도 방향" 자체를 전송합니다.
            state.motor_moving = True
            esp._send(f"JOG {x:.3f} {y:.3f}\n")
            
    return "OK"

@bp.route('/set_input_mode')
def set_input_mode():
    mode = request.args.get('mode', 'joystick')
    if mode in ('joystick', 'pointer', 'auto'):
        state.input_mode = mode
        import motor_esp32 as esp
        if mode == 'auto':
            state.control_mode = 'auto'
            if state.motor_connected:
                esp.set_mode("track")
        else:
            state.control_mode = 'manual'
            if state.motor_connected:
                if mode == 'joystick':
                    esp.set_mode("pos")
                    # 트래킹 모드나 다른 동작 후 조이스틱 모드로 돌아올 때,
                    # 가상 타겟이 엉뚱한 곳에 남아있어 모터가 순간이동(스냅)하는 것을 방지합니다.
                    state.last_queued_target_m1 = state.esp32_pos_m1_deg
                    state.last_queued_target_m2 = state.esp32_pos_m2_deg
                else:
                    esp.set_mode("track")
    return "OK"


@bp.route('/set_device_type')
def set_device_type():
    dtype = request.args.get('type', 'esp32')
    if dtype in ('esp32', 'arduino'):
        state.device_type = dtype
    return "OK"


@bp.route('/reconnect_esp32')
def reconnect_esp32():
    import motor_esp32 as esp
    port = request.args.get('port', None)
    try:
        esp.safe_disconnect()
        esp.connect(port)
        if state.motor_connected:
            return jsonify(ok=True, port=state.motor_port)
        return jsonify(ok=False, port=""), 503
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@bp.route('/available_ports')
def available_ports():
    try:
        import serial.tools.list_ports
        ports = [{"device": p.device, "description": p.description}
                 for p in serial.tools.list_ports.comports()]
    except Exception:
        ports = []
    return jsonify(ports=ports, connected=state.motor_connected,
                   current_port=state.motor_port)


@bp.route('/set_limit')
def set_limit():
    """사용자가 모터를 원하는 끝 위치로 직접 이동 후 호출 → 현재 ESP32 각도를 리밋으로 저장.
    ?axis=m1|m2  ?end=min|max
    """
    axis = request.args.get('axis', '').lower()   # 'm1' or 'm2'
    end  = request.args.get('end', '').lower()    # 'min' or 'max'

    if axis == 'm2' and end == 'max':
        state.soft_limit_m2_max = state.esp32_pos_m2_deg
        return jsonify(ok=True, axis='m2', end='max', value=state.soft_limit_m2_max)
    elif axis == 'm2' and end == 'min':
        state.soft_limit_m2_min = state.esp32_pos_m2_deg
        return jsonify(ok=True, axis='m2', end='min', value=state.soft_limit_m2_min)
    elif axis == 'm1' and end == 'max':
        state.soft_limit_m1_max = state.esp32_pos_m1_deg
        return jsonify(ok=True, axis='m1', end='max', value=state.soft_limit_m1_max)
    elif axis == 'm1' and end == 'min':
        state.soft_limit_m1_min = state.esp32_pos_m1_deg
        return jsonify(ok=True, axis='m1', end='min', value=state.soft_limit_m1_min)
    return jsonify(ok=False, error='invalid axis/end'), 400


@bp.route('/get_limits')
def get_limits():
    """현재 저장된 리밋 값을 전달 — UI 상태 미러링용."""
    return jsonify(
        m1_min=state.soft_limit_m1_min,
        m1_max=state.soft_limit_m1_max,
        m2_min=state.soft_limit_m2_min,
        m2_max=state.soft_limit_m2_max,
        m1_now=state.esp32_pos_m1_deg,
        m2_now=state.esp32_pos_m2_deg,
    )


@bp.route('/clear_limit')
def clear_limit():
    """?axis=m1|m2|all  ?end=min|max|all — 선택한 리밋 해제."""
    axis = request.args.get('axis', 'all').lower()
    end  = request.args.get('end',  'all').lower()
    if axis in ('m2', 'all'):
        if end in ('max', 'all'): state.soft_limit_m2_max = None
        if end in ('min', 'all'): state.soft_limit_m2_min = None
    if axis in ('m1', 'all'):
        if end in ('max', 'all'): state.soft_limit_m1_max = None
        if end in ('min', 'all'): state.soft_limit_m1_min = None
    return jsonify(ok=True)
