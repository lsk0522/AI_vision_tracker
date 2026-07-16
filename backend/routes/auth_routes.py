"""회원가입 및 인증 관련 라우트."""
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import re

bp = Blueprint('auth', __name__)

# 가상의 In-Memory 데이터베이스 (이메일이 키)
USERS_DB = {}

def check_password_complexity(password):
    """비밀번호 복잡도 검증
    - 최소 8자 이상
    - 영문 대문자 최소 1개
    - 영문 소문자 최소 1개
    - 숫자 최소 1개
    - 특수문자 최소 1개
    """
    if len(password) < 8:
        return False, "비밀번호는 최소 8자 이상이어야 합니다."
    if not re.search(r"[A-Z]", password):
        return False, "비밀번호는 영문 대문자를 최소 1개 이상 포함해야 합니다."
    if not re.search(r"[a-z]", password):
        return False, "비밀번호는 영문 소문자를 최소 1개 이상 포함해야 합니다."
    if not re.search(r"\d", password):
        return False, "비밀번호는 숫자를 최소 1개 이상 포함해야 합니다."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "비밀번호는 특수문자를 최소 1개 이상 포함해야 합니다."
    return True, "Valid"

@bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "요청 본문이 비어있습니다."}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"status": "error", "message": "이메일과 비밀번호를 모두 입력해주세요."}), 400

    # 1. 이메일 중복 체크
    if email in USERS_DB:
        return jsonify({"status": "error", "message": "이미 존재하는 이메일입니다."}), 400

    # 2. 비밀번호 복잡도 검증
    is_valid, msg = check_password_complexity(password)
    if not is_valid:
        return jsonify({"status": "error", "message": msg}), 400

    # 검증 통과 - 가입 처리 (In-Memory 저장 + 비밀번호 해싱)
    USERS_DB[email] = {
        "email": email,
        "password": generate_password_hash(password)
    }

    return jsonify({"status": "ok", "message": "회원가입이 완료되었습니다."}), 201


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "요청 본문이 비어있습니다."}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"status": "error", "message": "이메일과 비밀번호를 모두 입력해주세요."}), 400

    # 1. 사용자 존재 여부 및 비밀번호 일치 검증
    user = USERS_DB.get(email)
    if not user or not check_password_hash(user['password'], password):
        return jsonify({"status": "error", "message": "이메일 또는 비밀번호가 올바르지 않습니다."}), 401

    return jsonify({"status": "ok", "message": "로그인에 성공했습니다."}), 200
