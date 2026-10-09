@echo off
rem Upload Jarvis from this PC to a private GitHub repository (tagiriskaliev18-hash/jarvis).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Upload-Jarvis.ps1" %*
echo.
pause
