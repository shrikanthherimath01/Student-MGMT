@echo off
echo Starting WhatsApp Bridge...
start cmd /k "cd C:\StudentManagementSystem\sms && node server.js"
timeout /t 5
echo Starting Flask App...
start cmd /k "cd C:\StudentManagementSystem\sms && venv\Scripts\activate && python app.py"
echo Both started!
pause