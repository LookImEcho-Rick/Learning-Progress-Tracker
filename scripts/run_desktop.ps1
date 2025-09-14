$ErrorActionPreference = 'Stop'

Write-Host 'Ensuring virtual environment exists...'
if (-not (Test-Path .venv)) {
  python -m venv .venv
}

Write-Host 'Installing dependencies (requirements.txt)...'
& .\.venv\Scripts\python -m pip install --upgrade pip | Out-Host
& .\.venv\Scripts\pip install -r requirements.txt | Out-Host

Write-Host 'Launching Desktop app...'
& .\.venv\Scripts\python -m desktop.main
