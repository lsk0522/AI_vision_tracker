#!/bin/bash

echo ":: Pulling latest changes from GitHub..."
git stash
git pull origin main

echo ":: Updating dependencies..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
    pip install -r requirements.txt
else
    ./install.sh
fi

echo ":: Update Complete! Run ./start.sh to start."