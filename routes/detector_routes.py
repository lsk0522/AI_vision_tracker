"""검출·학습·갤러리 라우트."""
import os
import base64
import cv2
from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import safe_join
import state

bp = Blueprint('detector', __name__)


# ── 갤러리 ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
PICTURE_DIR = os.path.join(PROJECT_DIR, "picture")

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
    pic_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'picture')
    return send_from_directory(pic_dir, filename)


@bp.route('/delete/<path:filename>')
def delete_picture(filename):
    import os
    pic_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'picture')
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
        try:
            with open("/tmp/debug_T.log", "a") as f:
                f.write(f"[{time.time():.3f}] set_target rejected (control_mode={state.control_mode})\n")
        except:
            pass
        return jsonify({"status": "paused"})
    
    import time
    tx = request.args.get('tx', type=int)
    ty = request.args.get('ty', type=int)
    
    try:
        with open("/tmp/debug_T.log", "a") as f:
            f.write(f"[{time.time():.3f}] set_target received: tx={tx}, ty={ty}\n")
    except:
        pass
        
    if tx is not None and ty is not None:
        now = time.time()

        # ── 가상 포인트 스무딩 (Virtual Point Smoothing) ──────────
        # 화면 중앙(320,240)의 보이지 않는 가상 점이 타겟을 부드럽게 추적합니다.
        # 1.0초 이상 갱신이 없었으면(타겟 소실 후 재획득) 가상 점을 중앙으로 리셋합니다.
        last_time = getattr(state, 'remote_tracking_last_time', 0.0)
        gap = (now - last_time) > 1.0

        if gap or not hasattr(state, '_smooth_tx'):
            state._smooth_tx = 320.0
            state._smooth_ty = 240.0
            # 갭 발생 시 모터 즉시 정지 (중앙 = 에러 없음)
            state.point[0] = 320
            state.point[1] = 240

        # 1차 저주파 필터 (Alpha=0.12) — 가상 점이 타겟을 천천히 따라감
        alpha = 0.12
        state._smooth_tx += alpha * (float(tx) - state._smooth_tx)
        state._smooth_ty += alpha * (float(ty) - state._smooth_ty)

        # 에러 클램핑: 중앙에서 ±80px 이내로 제한 (급발진 방지)
        center_x, center_y = 320, 240
        err_x = state._smooth_tx - center_x
        err_y = state._smooth_ty - center_y
        err_x = max(-80.0, min(80.0, err_x))
        err_y = max(-80.0, min(80.0, err_y))

        state.point[0] = int(center_x + err_x)
        state.point[1] = int(center_y + err_y)

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
