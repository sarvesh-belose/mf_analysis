# Mutual Fund Analysis - Stop all running services (Backend & Frontend)

Write-Host "`nStopping Backend (Python)..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Stopping Frontend (Node/Vite)..." -ForegroundColor Yellow
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "`nSuccessfully terminated all MF Analysis services.`n" -ForegroundColor Green
