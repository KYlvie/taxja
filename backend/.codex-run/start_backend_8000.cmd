@echo off
setlocal
cd /d "C:\Users\yk1e25\OneDrive - University of Southampton\Documents\kiro\backend"
start "" "C:\Users\yk1e25\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
endlocal
