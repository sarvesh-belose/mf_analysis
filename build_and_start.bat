@echo off
setlocal

echo [1/2] Building Frontend (React/Vite)...
cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed.
    exit /b %errorlevel%
)
cd ..

echo.
echo [2/2] Starting Backend (Serving SPA from /dist)...
cd backend
python run.py
cd ..

pause
