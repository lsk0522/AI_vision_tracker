#!/usr/bin/env bash
# (라즈베리파이에서 실행) hand_tracker.py 실행 도우미
#  - 가상환경(.venv) 자동 사용
#  - main.py(웹 대시보드)가 켜져 있으면 알려 주고, 원하면 종료 (카메라/시리얼 충돌 방지)
cd "$(dirname "$0")" || exit 1

PY=python3
for v in .venv ../.venv ../../.venv; do
    if [ -x "$v/bin/python" ]; then PY="$v/bin/python"; break; fi
done

PIDS=$(pgrep -f "python[0-9.]* .*main\.py|python[0-9.]* main\.py" || true)
if [ -n "$PIDS" ]; then
    echo "⚠ main.py(웹 대시보드)가 실행 중입니다. 카메라와 ESP32를 같이 쓸 수 없습니다."
    ps -o pid,args -p $PIDS | sed 's/^/   /'
    read -r -p "main.py 를 종료하고 진행할까요? (모터 전류도 해제됩니다) [y/N] " a
    if [[ "$a" =~ ^[yY] ]]; then
        kill -INT $PIDS 2>/dev/null
        for _ in 1 2 3 4 5 6; do sleep 0.5; pgrep -f "main\.py" >/dev/null || break; done
    else
        exit 1
    fi
fi

if ! "$PY" -c "import mediapipe" 2>/dev/null; then
    echo "❌ mediapipe 가 설치되어 있지 않습니다:  $PY -m pip install mediapipe"
    exit 1
fi

exec "$PY" hand_tracker.py "$@"
