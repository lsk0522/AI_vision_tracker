"""routes 패키지 — 4개 Blueprint를 Flask app에 등록."""
from .core import bp as core_bp
from .camera_routes import bp as camera_bp
from .detector_routes import bp as detector_bp
from .motor_routes import bp as motor_bp


def setup_routes(app):
    app.register_blueprint(core_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(detector_bp)
    app.register_blueprint(motor_bp)
