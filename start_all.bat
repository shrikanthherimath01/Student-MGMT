@echo off
title SCHOOL MANAGEMENT SYSTEM
color 0A

echo ========================================
echo   STARTING SCHOOL MANAGEMENT SYSTEM
echo ========================================
echo.

cd /d "C:\StudentManagementSystem\sms"

echo [1/3] Starting WhatsApp Bridge...

:: Try to find Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found!
    echo Please install Node.js from https://nodejs.org/
    echo.
    pause
    exit /b
)

:: Start WhatsApp bridge
start "WhatsApp Bridge" /min cmd /c "node server.js"

echo [2/3] Waiting for bridge to start...
timeout /t 8 /nobreak >nul

echo [3/3] Starting Flask Application...
echo.
echo ========================================
echo   SYSTEM READY!
echo ========================================
echo 🌐 Open: http://localhost:5000
echo 📧 Admin: admin@school.edu / Admin@123
echo 📱 FIRST TIME: Check minimized window for QR code
echo ========================================
echo.

call venv\Scripts\activate
python app.py

pause