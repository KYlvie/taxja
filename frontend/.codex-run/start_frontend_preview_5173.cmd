@echo off
setlocal
cd /d "C:\Users\yk1e25\OneDrive - University of Southampton\Documents\kiro\frontend"
start "" "C:\Program Files\nodejs\node.exe" ".\node_modules\vite\bin\vite.js" preview --host 0.0.0.0 --port 5173
endlocal
