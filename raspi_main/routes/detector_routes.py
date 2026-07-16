"""검출·학습·갤러리 라우트."""
import os
import base64
import time
import threading
import cv2
from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import safe_join
import state

bp = Blueprint('detector', __name__)


# ── 타겟 소실 감시 워치독 ─────────────────────────────────
# set_target이 1초 이상 호출되지 않으면 state.point를 중앙으로 리셋 → 모터 정지
def _target_loss_watchdog():
    while True:
        time.sleep(0.2)
        try:
            if state.control_mode == "auto":
                last = getattr(state, 'remote_tracking_last_time', 0.0)
                if last > 0 and (time.time() - last) > 1.0:
                    state.point[0] = 320
                    state.point[1] = 240
                    if hasattr(state, '_smooth_tx'):
                        state._smooth_tx = 320.0
                        state._smooth_ty = 240.0
        except:
            pass

_watchdog = threading.Thread(target=_target_loss_watchdog, daemon=True)
_watchdog.start()


# ── 갤러리 ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
PICTURE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "data", "picture")

@bp.route('/captures')
def list_captures():
    folder = PICTURE_DIR
    if not os.path.exists(folder):
        return jsonify([])
    try:
        files = [f for f in os.listdir(folder)
                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(folder, x)), reverse=True)
        return jsonify(files)
    except Exception:
        return jsonify([])


@bp.route('/picture/<path:filename>')
def serve_picture(filename):
    import os
    from flask import send_from_directory
    pic_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'picture')
    return send_from_directory(pic_dir, filename)


@bp.route('/delete/<path:filename>')
def delete_picture(filename):
    import os
    pic_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'picture')
    file_path = safe_join(pic_dir, filename)
    if file_path is None:
        return jsonify({"status": "error", "message": "Invalid filename"}), 400
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "error", "message": "File not found"}), 404


# ── 추적 상태 ─────────────────────────────────────────────
@bp.route('/ball')
def ball():
    if state.ball is None:
        return jsonify(detected=False)
    return jsonify(detected=True, lost=state.ball_lost, **state.ball)


@bp.route('/tracking_status')
def tracking_status():
    locked = (state.ball is not None and not state.ball_lost
              and state.tracking_mode == "custom")
    return jsonify(
        locked=locked,
        detected=(state.ball is not None),
        tracking_mode=state.tracking_mode,
        control_mode=state.control_mode,
    )


@bp.route('/set_target', methods=['GET', 'POST'])
def set_target():
    """노트북 등 외부(원격) 기기에서 YOLO 검출 결과를 받아오는 엔드포인트"""
    # 수동(조이스틱) 모드일 때는 즉시 거부하여 Flask 부하를 없앰
    if state.control_mode != "auto":
        return jsonify({"status": "paused"})

    tx = request.args.get('tx', type=int)
    ty = request.args.get('ty', type=int)

    if tx is not None and ty is not None:
        now = time.time()

        # ── 가상 포인트 스무딩 (Virtual Point Smoothing) ──────────
        # 보이지 않는 가상 점이 타겟을 부드럽게 추적합니다.
        # state.point 는 이 함수(+아래 워치독)만 갱신합니다 — detector 루프는 관여하지 않음.
        # 1.0초 이상 갱신이 없었으면(타겟 소실 후 재획득) 가상 점을 중앙으로 리셋합니다.
        # 오차 계산은 실제 프레임 중심 기준(해상도 무관), 전송 좌표는 ESP32 펌웨어
        # 계약(중심 320:240 고정)에 맞춰 재구성합니다.
        frame = state.current_frame
        if frame is not None:
            frame_h, frame_w = frame.shape[:2]
            center_x, center_y = frame_w / 2.0, frame_h / 2.0
        else:
            center_x, center_y = 320.0, 240.0

        last_time = getattr(state, 'remote_tracking_last_time', 0.0)
        gap = (now - last_time) > 1.0
        dt = now - last_time
        if dt < 0.001:
            dt = 0.001

        if gap or not hasattr(state, '_smooth_tx') or not hasattr(state, '_integral_x'):
            state._smooth_tx = center_x
            state._smooth_ty = center_y
            state._integral_x = 0.0
            state._integral_y = 0.0
            state._prev_err_x = 0.0
            state._prev_err_y = 0.0
            state.point[0] = 320
            state.point[1] = 240

        Kp = 0.15
        Ki = 0.01
        Kd = 0.05
        windup_limit = 100.0

        err_x = float(tx) - state._smooth_tx
        err_y = float(ty) - state._smooth_ty

        state._integral_x += err_x * dt
        state._integral_y += err_y * dt
        state._integral_x = max(-windup_limit, min(windup_limit, state._integral_x))
        state._integral_y = max(-windup_limit, min(windup_limit, state._integral_y))

        derivative_x = (err_x - state._prev_err_x) / dt
        derivative_y = (err_y - state._prev_err_y) / dt

        output_x = (Kp * err_x) + (Ki * state._integral_x) + (Kd * derivative_x)
        output_y = (Kp * err_y) + (Ki * state._integral_y) + (Kd * derivative_y)

        state._smooth_tx += output_x
        state._smooth_ty += output_y

        state._prev_err_x = err_x
        state._prev_err_y = err_y

        offset_x = state._smooth_tx - center_x
        offset_y = state._smooth_ty - center_y
        offset_x = max(-80.0, min(80.0, offset_x))
        offset_y = max(-80.0, min(80.0, offset_y))

        state.point[0] = 320 + int(offset_x)
        state.point[1] = 240 + int(offset_y)

        state.remote_tracking_last_time = now
        state.ball = {
            "cx": tx,
            "cy": ty,
            "x": tx - 10,
            "y": ty - 10,
            "w": 20,
            "h": 20,
            "conf": 1.0,
            "predicted": False,
            "detector": "remote"
        }
        state.ball_lost = False
    return jsonify({"status": "ok"})


@bp.route('/api/status/monitor', methods=['GET'])
def api_status_monitor():
    """모터 안전 제한 상태 및 비전 조준 오차 모니터링 API"""
    limit_msg = getattr(state, 'active_limit_msg', "")
    limit_active = bool(limit_msg)
    
    # 조준점 편차 계산 (화면 중심 320, 240 기준)
    curr_point = getattr(state, 'point', [320, 240])
    target_error_x = curr_point[0] - 320
    target_error_y = curr_point[1] - 240
    
    return jsonify({
        "limit_active": limit_active,
        "limit_message": limit_msg,
        "target_error_x": target_error_x,
        "target_error_y": target_error_y,
        "current_point": curr_point
    }), 200
