@echo off
chcp 65001 > nul
echo ========================================================
echo   AI Vision Tracker - Laptop Remote Engine
echo ========================================================
echo.

:: 설정 정보 (하드코딩)
set RASPI_IP=172.30.14.31

echo [안내] 먼저 라즈베리파이에서 ./start.sh 가 켜져 있어야 합니다!
echo.
echo [알림] 노트북에서 AI 객체 인식 트래커를 시작합니다...
echo.

python remote_tracker.py --ip %RASPI_IP%

echo.
echo 모든 작업이 종료되었습니다. 아무 키나 누르면 닫힙니다.
pause > nul
