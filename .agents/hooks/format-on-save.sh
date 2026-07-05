#!/bin/bash
# 이 스크립트는 Python 파일들의 포맷을 맞춰주는 Hook입니다.
# autopep8 또는 black을 사용하여 코드를 정리합니다.

if command -v black >/dev/null 2>&1; then
    echo "Running Black formatter..."
    black .
else
    echo "Black is not installed. You can install it via 'pip install black'"
    exit 1
fi
