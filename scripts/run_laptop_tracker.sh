#!/usr/bin/env bash
# Mac/Linux용: 노트북에서 AI 추적을 돌리고 라즈베리파이로 결과를 보내는 원격 트래커 실행
# 사용법: ./scripts/run_laptop_tracker.sh [IP]
#   IP를 생략하면 라즈베리파이를 자동으로 찾습니다 (scripts/find_pi.py).
#   필요 패키지: pip3 install ultralytics opencv-python requests numpy

echo "========================================================"
echo "  AI Vision Tracker - Laptop Remote Engine"
echo "========================================================"
echo

# 저장소 루트에서 실행 (모델 경로 data/best_int8.tflite 기준)
cd "$(dirname "$0")/.." || exit 1

if [ -n "$1" ]; then
    echo "Starting Laptop AI Remote Tracker targeting $1..."
    python3 backend/remote_tracker.py --ip "$1"
else
    echo "Starting Laptop AI Remote Tracker (라즈베리파이 자동 탐색)..."
    python3 backend/remote_tracker.py
fi

echo
echo "Finished."
