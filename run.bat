@echo off
title MediAssist Server
cd /d "%~dp0"
echo Starting MediAssist...
echo.
echo Server will be available at: http://localhost:8000
echo.
.\.venv\Scripts\uvicorn app:app --host 127.0.0.1 --port 8000
pause
