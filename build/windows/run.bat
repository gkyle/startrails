@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0src\setup\setup.ps1" -Packaged -Launch -ProjectPath "%~1"
exit /b %errorlevel%
