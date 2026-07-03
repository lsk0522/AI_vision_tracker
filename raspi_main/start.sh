#!/bin/bash

# ==========================================
# AI Vision Tracker - Start Script
# ==========================================

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "[!] Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Optional: Disable OpenCV GUI warnings in headless mode
export QT_QPA_PLATFORM=offscreen

# Check if waitress is installed, if not fallback to flask dev server
if ! python -c "import waitress" &> /dev/null; then
    echo ":: [Warning] waitress not found. Falling back to Flask dev server."
fi

# Run the CLI loading sequence and start the main program
# We will execute main.py directly, which will handle the animation and start waitress
python main.py
