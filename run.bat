@echo off
powershell.exe -ExecutionPolicy Bypass -File "src/setup/setup.ps1"

echo Starting StarTrails AI...
uv run --no-sync src/main.py