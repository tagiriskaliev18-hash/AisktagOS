@echo off
rem Wrapper to open Instagram Reel via Antigravity helper
set REEL_URL=%1
if "%REEL_URL%"=="" (
    echo Usage: ai-reel.bat <instagram-reel-url>
    exit /b 1
)
python "C:\Users\user\Desktop\AIskTagOS\tools\view_instagram_reel.py" "%REEL_URL%"
