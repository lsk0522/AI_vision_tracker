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
pip install -r requirements.txt

echo ":: [4/4] Installation Complete!"
echo ""
echo "To start the tracker, simply run: ./start.sh"