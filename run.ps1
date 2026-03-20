#!/usr/bin/env powershell
# MediAssist Launcher Script
Write-Host "Starting MediAssist v4.1..." -ForegroundColor Cyan
Write-Host "Server will be available at: http://localhost:8001" -ForegroundColor Yellow
Write-Host ""

# Run the server
& .\.venv\Scripts\uvicorn app:app --host 127.0.0.1 --port 8001
