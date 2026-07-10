@echo off
echo ========================================================
echo   AI Vision Tracker - Laptop Remote Engine
echo ========================================================
echo.

set RASPI_IP=172.30.14.31

echo [Info] Please make sure ./start.sh is running on your Raspberry Pi!
echo.
echo Starting Laptop AI Remote Tracker...
echo.

python remote_tracker.py --ip %RASPI_IP%

echo.
echo Finished. Press any key to exit.
pause > nul
