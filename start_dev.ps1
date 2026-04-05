# Mutual Fund Analysis - Start Development (Side-by-Side)

Write-Host "`n[1/2] Starting Backend Server..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python run.py"

Write-Host "[2/2] Starting Frontend (Vite) Dev..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "`nApplication running in two separate PowerShell windows." -ForegroundColor Yellow
Write-Host "Backend URL: http://localhost:8000/api/health"
Write-Host "Frontend URL: http://localhost:5173/"
Write-Host "Initial Setup Required? If first run, please visit http://localhost:5173/ and use the Setup Wizard.`n"
