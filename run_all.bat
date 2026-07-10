@echo off
echo ========================================================
echo   AI Vision Tracker - One-Click Launcher (Remote Mode)
echo ========================================================
echo.

set RASPI_IP=172.30.14.31
set RASPI_ID=pi30306

echo Starting Raspberry Pi Server (%RASPI_ID%@%RASPI_IP%)...
echo (Please enter SSH password if prompted in the new window)
echo.

start "Raspberry Pi Server" ssh -t %RASPI_ID%@%RASPI_IP% "cd ~/AI_vision_tracker && git pull origin dev && ./start.sh"

echo Waiting 5 seconds for the server to start...
timeout /t 5 > nul

echo.
echo Starting Laptop AI Remote Tracker...
python remote_tracker.py --ip %RASPI_IP%

echo.
echo Finished. Press any key to exit.
pause > nul
