# Setup script for MF Analysis project

Write-Host "`n[1/2] Installing Backend Dependencies..." -ForegroundColor Green
cd backend
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error installing backend dependencies."
    exit $LASTEXITCODE
}
cd ..

Write-Host "[2/2] Installing Frontend Dependencies..." -ForegroundColor Green
cd frontend
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error installing frontend dependencies."
    exit $LASTEXITCODE
}
cd ..

Write-Host "`nSetup completed successfully!`n" -ForegroundColor Yellow
Write-Host "To run in Development:  ./start_dev.ps1"
Write-Host "To run in Production:   ./build_and_start.ps1"
Write-Host "`nReady to go."
