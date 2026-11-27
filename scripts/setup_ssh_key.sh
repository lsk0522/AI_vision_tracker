#!/usr/bin/env bash
# Mac/Linux용: 비밀번호 없이 라즈베리파이에 SSH 접속하기 위한 1회성 셋업
#   1) SSH 키 생성  2) 파이에 키 등록  3) 접속 테스트
#   4) 파이 호스트 키 고정 (IP가 바뀌어도 자동으로 찾도록)  5) `ssh pi` 별칭 등록
# 사용법: ./scripts/setup_ssh_key.sh [IP] [사용자명]
#   IP를 생략하면 자동으로 찾습니다.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PI_USER="${2:-pi30306}"
KEY="$HOME/.ssh/id_ed25519"

if [ -n "$1" ]; then
    PI_IP="$1"
else
    echo "라즈베리파이를 찾는 중..."
    PI_IP="$(python3 "$SCRIPT_DIR/find_pi.py" || true)"
    if [ -z "$PI_IP" ]; then
        echo "❌ 자동으로 못 찾았습니다. Pi Connect 셸에서 'hostname -I' 로 IP를 확인한 뒤:"
        echo "   ./scripts/setup_ssh_key.sh <IP>"
        exit 1
    fi
fi

echo "========================================================"
echo "  비밀번호 없이 자동 접속하기 위한 1회성 셋업"
echo "  대상: ${PI_USER}@${PI_IP}"
echo "========================================================"
echo

echo "1. Mac에 보안 인증키를 생성합니다..."
if [ ! -f "$KEY" ]; then
    mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
    ssh-keygen -t ed25519 -f "$KEY" -N ""
else
    echo "이미 인증키가 존재합니다. 생략합니다."
fi
echo

echo "2. 라즈베리파이에 인증키를 등록합니다."
echo "※ 라즈베리파이 비밀번호를 '딱 한 번만' 입력해주세요! (입력 중 화면에 안 보이는 게 정상입니다)"
ssh-copy-id -i "${KEY}.pub" "${PI_USER}@${PI_IP}"
echo

echo "3. 접속 테스트..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "${PI_USER}@${PI_IP}" "echo '✅ 비밀번호 없이 접속 성공: ' \$(hostname)"; then
    echo "❌ 키 인증 접속에 실패했습니다. 위 메시지를 확인해주세요."
    exit 1
fi
echo

echo "4. 이 파이를 '내 파이'로 고정합니다 (IP가 바뀌어도 자동 탐색)..."
python3 "$SCRIPT_DIR/find_pi.py" --pin --ip "$PI_IP" --user "$PI_USER" >/dev/null
echo

echo "5. 'ssh pi' 별칭을 등록합니다..."
bash "$SCRIPT_DIR/install_ssh_alias.sh" "$PI_USER"
echo
echo "설정이 완료되었습니다! 앞으로는 IP가 바뀌어도  ssh pi  로 접속하세요."
