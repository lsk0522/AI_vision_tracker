#!/bin/bash

# ==========================================
# AI Vision Tracker - Raspberry Pi Installer
# ==========================================

echo ":: [1/4] Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip libgl1-mesa-glx libglib2.0-0 arduino-cli git

echo ":: [2/4] Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo ":: [3/4] Installing Python dependencies..."
pip install --upgrade pip
# ultralytics와 그 의존성(torch 등 1GB 이상)은 라즈베리파이 용량을 고갈시키므로 설치에서 제외합니다.
grep -v "ultralytics" requirements.txt > req_pi.txt
pip install -r req_pi.txt
rm req_pi.txt

echo ":: [4/4] Installation Complete!"
echo ""
echo "To start the tracker, simply run: ./start.sh"