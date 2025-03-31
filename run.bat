@echo off
powershell -c "src/setup/setup.ps1"

echo Starting StarTrails AI...
uv run src/main.py