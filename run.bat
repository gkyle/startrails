@echo off
powershell -c "src/setup/setup.ps1"

echo Starting StarStack AI...
uv run src/main.py