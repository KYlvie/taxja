# Taxja Quick Start Guide (Development Mode)

## Prerequisites
- Docker Desktop (running)
- Python 3.11+
- Node.js 20+

## Quick Start (3 Steps)

### Step 1: Setup Environment
```powershell
.\start-dev.ps1
```
This will:
- Start infrastructure (PostgreSQL, Redis, MinIO)
- Create Python virtual environment
- Install dependencies
- Run database migrations

### Step 2: Start Services
```powershell
.\start-services.ps1
```
This will:
- Start backend in a new window
- Start frontend in a new window
- Open browser automatically

### Step 3: Access Application
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Manual Start (Alternative)

If you prefer to start services manually:

### Terminal 1 - Backend
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

### Terminal 2 - Frontend
```powershell
cd frontend
npm run dev
```

## Development Benefits
- Hot reload enabled (code changes apply immediately)
- No need to rebuild Docker images
- Easy debugging
- Fast iteration

## Stop Services
- Close the PowerShell windows
- Or press Ctrl+C in each terminal

## Troubleshooting

### Docker not running
```powershell
# Start Docker Desktop from Windows Start Menu
```

### Port already in use
```powershell
# Check what's using the port
netstat -ano | findstr :8000
# Kill the process (replace PID)
taskkill /PID <PID> /F
```

### Database connection error
```powershell
# Restart infrastructure
docker-compose restart postgres redis minio
```

### Clean restart
```powershell
# Stop all services
docker-compose down -v
# Run setup again
.\start-dev.ps1
```

## Project Structure
```
taxja/
├── backend/          # FastAPI backend
├── frontend/         # React frontend
├── start-dev.ps1     # Setup script
└── start-services.ps1 # Auto-start script
```

## Next Steps
- Read API documentation at http://localhost:8000/docs
- Explore the frontend at http://localhost:5173
- Check backend logs in the backend terminal
- Check frontend logs in the frontend terminal
