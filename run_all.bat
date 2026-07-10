@echo off
chcp 65001 > nul
echo ========================================================
echo   AI Vision Tracker - One-Click Launcher (Remote Mode)
echo ========================================================
echo.

:: 1. 설정 정보 입력받기
set /p RASPI_IP="1. 라즈베리파이 IP 주소를 입력하세요 (기본값: 192.168.0.28): "
if "%RASPI_IP%"=="" set RASPI_IP=192.168.0.28

set /p RASPI_ID="2. 라즈베리파이 접속 아이디를 입력하세요 (기본값: pi): "
if "%RASPI_ID%"=="" set RASPI_ID=pi

echo.
echo [알림] 라즈베리파이(%RASPI_ID%@%RASPI_IP%)에서 서버를 시작합니다...
echo (SSH 비밀번호를 물어보면 입력해주세요!)
echo.

:: 2. 라즈베리파이에 SSH 접속하여 자동 업데이트(git pull) 후 ./start.sh 실행 (새 창에서 띄움)
start "Raspberry Pi Server" ssh -t %RASPI_ID%@%RASPI_IP% "cd ~/AI_vision_tracker-main && git pull origin dev && ./start.sh"

echo 라즈베리파이 서버가 켜질 때까지 5초 대기합니다...
timeout /t 5 > nul

:: 3. 노트북에서 원격 트래커 실행 (AI 계산)
echo.
echo [알림] 노트북에서 AI 객체 인식 트래커를 시작합니다...
python remote_tracker.py --ip %RASPI_IP%

echo.
echo 모든 작업이 종료되었습니다. 아무 키나 누르면 닫힙니다.
pause > nul
