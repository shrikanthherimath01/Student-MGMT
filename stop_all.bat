@echo off
color 0C
echo ========================================
echo   STOPPING ALL SERVICES
echo ========================================
echo.

echo Stopping WhatsApp bridge...
taskkill /f /im node.exe >nul 2>nul

echo Stopping Flask server...
taskkill /f /im python.exe >nul 2>nul

echo.
echo ✅ All services stopped!
echo.
timeout /t 2 /nobreak >nul
exit