# Taxja Services Auto-Start Script
# Starts both backend and frontend services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting Taxja Development Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get project root directory
$rootDir = $PSScriptRoot

# Start backend
Write-Host "[1/2] Starting backend service..." -ForegroundColor Yellow
$backendPath = Join-Path $rootDir "backend"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$backendPath'; & .\venv\Scripts\Activate.ps1; Write-Host 'Backend service starting...' -ForegroundColor Green; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
) -WindowStyle Normal

Write-Host "Backend service started in new window" -ForegroundColor Green
Start-Sleep -Seconds 3

# Start frontend
Write-Host ""
Write-Host "[2/2] Starting frontend service..." -ForegroundColor Yellow
$frontendPath = Join-Path $rootDir "frontend"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$frontendPath'; Write-Host 'Frontend service starting...' -ForegroundColor Green; npm run dev"
) -WindowStyle Normal

Write-Host "Frontend service started in new window" -ForegroundColor Green

# Wait for services to start
Write-Host ""
Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Open browser
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Services Started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Backend: http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Yellow

Start-Sleep -Seconds 5
Start-Process "http://localhost:5173"
Start-Process "http://localhost:8000/docs"

Write-Host ""
Write-Host "Tips:" -ForegroundColor Cyan
Write-Host "  - Backend and frontend run in separate windows" -ForegroundColor White
Write-Host "  - Code changes will auto-reload (hot reload)" -ForegroundColor White
Write-Host "  - Close windows to stop services" -ForegroundColor White
Write-Host "  - Check each window for logs" -ForegroundColor White
Write-Host ""
