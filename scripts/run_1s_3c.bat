@echo off
cd /d "%~dp0.."
echo "Starting 1 controller (server) and 3 player clients"
start "game1" cmd /k uv run src\controller_main.py &
timeout 1
start "game2" cmd /k uv run src\player_main.py &
timeout 1
start "game3" cmd /k uv run src\player_main.py &
timeout 1
start "game4" cmd /k uv run src\player_main.py &

echo "press any button to close all clients
pause
taskkill /f /t /fi "windowtitle eq game1*"
taskkill /f /t /fi "windowtitle eq game2*"
taskkill /f /t /fi "windowtitle eq game3*"
taskkill /f /t /fi "windowtitle eq game4*"
