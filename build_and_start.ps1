# Mutual Fund Analysis - Build & Start Production Server

Write-Host "`n[1/2] Building Frontend (React/Vite)..." -ForegroundColor Green
cd frontend
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend build failed."
    exit $LASTEXITCODE
}
cd ..

Write-Host "[2/2] Starting Backend (Serving dist/ from /root URL)..." -ForegroundColor Cyan
cd backend
python run.py
cd ..

Write-Host "Application is running! Frontend is being served by FastAPI now." -ForegroundColor Yellow
Write-Host "Visit: http://localhost:8000/"
