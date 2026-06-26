"""카메라 선택·설정 라우트."""
from flask import Blueprint, request, jsonify
import state

bp = Blueprint('camera', __name__)


@bp.route('/list_cameras')
def list_cameras():
    from camera import list_cameras as _list
    return jsonify(cameras=_list(max_test=6))


@bp.route('/set_camera')
def set_camera():
    from camera import set_camera_index
    index = int(request.args.get('index', 0))
    ok = set_camera_index(index)
    return jsonify(ok=ok, index=index)


@bp.route('/camera_settings')
def camera_settings():
    from camera import _camera_index, FRAME_W, FRAME_H, FRAME_FPS, _is_dummy, RESOLUTION_PRESETS, FPS_PRESETS
    return jsonify(
        index=_camera_index, width=FRAME_W, height=FRAME_H, fps=FRAME_FPS,
        is_dummy=_is_dummy, flip=state.flip_enabled,
        res_presets=RESOLUTION_PRESETS, fps_presets=FPS_PRESETS,
    )


@bp.route('/set_camera_resolution')
def set_camera_resolution():
    from camera import set_camera_resolution
    w = int(request.args.get('w', 640))
    h = int(request.args.get('h', 480))
    ok = set_camera_resolution(w, h)
    return jsonify(ok=ok, w=w, h=h)


@bp.route('/set_camera_fps')
def set_camera_fps():
    from camera import set_camera_fps
    fps = int(request.args.get('fps', 30))
    ok = set_camera_fps(fps)
    return jsonify(ok=ok, fps=fps)
