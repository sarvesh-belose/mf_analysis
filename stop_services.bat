@echo off
echo Stopping Backend (Python)...
taskkill /F /IM python.exe /T 2>nul
echo Stopping Frontend (Node/Vite)...
taskkill /F /IM node.exe /T 2>nul
echo Successfully terminated MF Analysis services.
pause
