#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
".venv/bin/python" -m pip install --upgrade pip
".venv/bin/pip" install -r requirements.txt

".venv/bin/pyinstaller" --noconfirm --windowed --name LearningProgressTracker --paths . desktop/main.py
echo "Build complete. See 'dist/LearningProgressTracker' for output."
