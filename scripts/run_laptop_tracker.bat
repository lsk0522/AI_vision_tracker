@echo off
echo ========================================================
echo   AI Vision Tracker - Laptop Remote Engine
echo ========================================================
echo.

set DEFAULT_IP=172.30.14.31
set /p RASPI_IP="Enter Raspberry Pi IP address [default: %DEFAULT_IP%]: "
if "%RASPI_IP%"=="" set RASPI_IP=%DEFAULT_IP%

echo.
echo Starting Laptop AI Remote Tracker targeting %RASPI_IP%...
echo.

python ..\backend\remote_tracker.py --ip %RASPI_IP%

echo.
echo Finished. Press any key to exit.
pause > nul
