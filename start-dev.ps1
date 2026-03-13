# Taxja Development Environment Setup Script
# For local development with hot reload

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Taxja Development Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker status
Write-Host "[1/6] Checking Docker status..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "Docker is running" -ForegroundColor Green
} catch {
    Write-Host "Docker is not running. Please start Docker Desktop first" -ForegroundColor Red
    exit 1
}

# Start infrastructure
Write-Host ""
Write-Host "[2/6] Starting infrastructure (PostgreSQL, Redis, MinIO)..." -ForegroundColor Yellow
docker-compose up -d postgres redis minio
Start-Sleep -Seconds 5

# Check infrastructure status
Write-Host ""
Write-Host "[3/6] Checking infrastructure status..." -ForegroundColor Yellow
docker-compose ps postgres redis minio

# Setup backend
Write-Host ""
Write-Host "[4/6] Setting up backend environment..." -ForegroundColor Yellow
Set-Location backend

# Check virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Check if dependencies need to be installed
$requirementsHash = Get-FileHash requirements.txt -Algorithm MD5
$installedHash = ""
if (Test-Path ".requirements.hash") {
    $installedHash = Get-Content ".requirements.hash"
}

if ($requirementsHash.Hash -ne $installedHash) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
    $requirementsHash.Hash | Out-File ".requirements.hash"
} else {
    Write-Host "Python dependencies are up to date" -ForegroundColor Green
}

# Check .env file
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    Copy-Item .env.example .env
}

# Run database migrations
Write-Host "Running database migrations..." -ForegroundColor Yellow
alembic upgrade head

Set-Location ..

# Setup frontend
Write-Host ""
Write-Host "[5/6] Setting up frontend environment..." -ForegroundColor Yellow
Set-Location frontend

# Check if dependencies need to be installed
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing Node.js dependencies..." -ForegroundColor Yellow
    npm install
} else {
    Write-Host "Node.js dependencies are installed" -ForegroundColor Green
}

Set-Location ..

# Display startup information
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now start the services:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Start backend (in new terminal):" -ForegroundColor Cyan
Write-Host "  cd backend" -ForegroundColor White
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  uvicorn app.main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "Start frontend (in new terminal):" -ForegroundColor Cyan
Write-Host "  cd frontend" -ForegroundColor White
Write-Host "  npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "Or run the auto-start script:" -ForegroundColor Cyan
Write-Host "  .\start-services.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Backend: http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
