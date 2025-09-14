$ErrorActionPreference = 'Stop'

if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python -m pip install --upgrade pip | Out-Host
& .\.venv\Scripts\pip install -r requirements.txt | Out-Host

& .\.venv\Scripts\pyinstaller --noconfirm --windowed --name LearningProgressTracker --paths . desktop\main.py
Write-Host "Build complete. See 'dist/LearningProgressTracker' for output."
