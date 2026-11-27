@echo off
chcp 65001 > nul
echo ========================================================
echo   비밀번호 없이 자동 접속하기 위한 1회성 셋업
echo ========================================================
echo.
set PI_USER=pi30306
set PI_IP=%1
if "%PI_IP%"=="" (
    echo 라즈베리파이를 찾는 중...
    for /f "delims=" %%i in ('python "%~dp0find_pi.py"') do set PI_IP=%%i
)
if "%PI_IP%"=="" (
    echo 자동으로 못 찾았습니다. 'setup_ssh_key.bat IP주소' 로 다시 실행해주세요.
    pause > nul
    exit /b 1
)
echo 대상: %PI_USER%@%PI_IP%
echo.
echo 1. 노트북에 보안 인증키를 생성합니다...
if not exist "%USERPROFILE%\.ssh\id_rsa" (
    ssh-keygen -t rsa -b 4096 -f "%USERPROFILE%\.ssh\id_rsa" -N ""
) else (
    echo 이미 인증키가 존재합니다. 생략합니다.
)
echo.
echo 2. 라즈베리파이에 인증키를 등록합니다.
echo ※ 여기서 라즈베리파이 비밀번호를 '딱 한 번만' 입력해주세요!
echo (비밀번호를 칠 때 화면에 안 보여도 정상적으로 입력되고 있습니다.)
type "%USERPROFILE%\.ssh\id_rsa.pub" | ssh %PI_USER%@%PI_IP% "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
echo.
echo 3. 이 파이를 '내 파이'로 고정합니다 (IP가 바뀌어도 자동 탐색)...
python "%~dp0find_pi.py" --pin --ip %PI_IP% --user %PI_USER%
echo.
echo 설정이 완료되었습니다! 이제 창을 닫고 run_laptop_tracker.bat을 실행해보세요.
pause > nul
