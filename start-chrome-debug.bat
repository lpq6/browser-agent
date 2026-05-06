@echo off
echo ============================================
echo   Chrome Remote Debugging Launcher
echo ============================================
echo.
echo Killing existing Chrome instances...
taskkill /IM chrome.exe /F 2>nul
timeout /t 2 /nobreak >nul

echo Starting Chrome with remote debugging on port 9222...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\tmp\chrome-debug"

echo.
echo Chrome started!
echo Debug URL: http://localhost:9222/json/version
echo.
pause
