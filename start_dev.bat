@echo off
setlocal

echo [1/2] Starting Backend Server...
start "Backend" /D backend python run.py

echo [2/2] Starting Frontend (Vite) Dev...
start "Frontend" /D frontend npm run dev

echo.
echo Application started in two separate windows.
echo Backend URL: http://localhost:8000/api/health
echo Frontend URL: http://localhost:5173/
echo.
pause
