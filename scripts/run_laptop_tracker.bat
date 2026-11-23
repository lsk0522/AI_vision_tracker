@echo off
echo ========================================================
echo   AI Vision Tracker - Laptop Remote Engine
echo ========================================================
echo.

rem Run from repo root so the model path data\best_int8.tflite resolves
cd /d "%~dp0.."

set RASPI_IP=
set /p RASPI_IP="Enter Raspberry Pi IP address [Enter = auto-detect]: "

echo.
if "%RASPI_IP%"=="" (
    echo Starting Laptop AI Remote Tracker ^(auto-detecting Raspberry Pi^)...
    python backend\remote_tracker.py
) else (
    echo Starting Laptop AI Remote Tracker targeting %RASPI_IP%...
    python backend\remote_tracker.py --ip %RASPI_IP%
)

echo.
echo Finished. Press any key to exit.
pause > nul
