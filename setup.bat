@echo off
setlocal

echo [1/2] Installing Backend Dependencies...
cd backend
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing backend dependencies.
    exit /b %errorlevel%
)
cd ..

echo [2/2] Installing Frontend Dependencies...
cd frontend
npm install
if %errorlevel% neq 0 (
    echo Error installing frontend dependencies.
    exit /b %errorlevel%
)
cd ..

echo.
echo Setup completed successfully!
echo.
echo To run in Development:  start_dev.bat
echo To run in Production:   build_and_start.bat
pause
