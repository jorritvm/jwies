@echo off
echo "Starting 4 player clients (of which one is the host)"
start "game1" cmd /k ..\.venv\Scripts\python.exe controller_main.py &
timeout 1
start "game2" cmd /k ..\.venv\Scripts\python.exe player_main.py &
timeout 1
start "game3" cmd /k ..\.venv\Scripts\python.exe player_main.py &
timeout 1
start "game4" cmd /k ..\.venv\Scripts\python.exe player_main.py &

echo "press any button to close all clients
pause
taskkill /f /t /fi "windowtitle eq game1*"
taskkill /f /t /fi "windowtitle eq game2*"
taskkill /f /t /fi "windowtitle eq game3*"
taskkill /f /t /fi "windowtitle eq game4*"
