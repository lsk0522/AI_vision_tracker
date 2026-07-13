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
        state.remote_tracking_last_time = time.time()
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
        # ── 직접 state.point 업데이트 (detector 스레드 의존 제거) ──
        # motor_esp32._run 루프는 state.point를 읽어 T:x:y를 전송합니다.
        # detector 스레드가 죽어있으면 state.point가 중앙(320,240)에서 안 바뀌어
        # T 명령이 전혀 나가지 않는 버그를 방지합니다.
        state.point[0] = tx
        state.point[1] = ty
    
    return jsonify({"status": "ok"})
