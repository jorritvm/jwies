echo "starting 4 player clients"
start cmd /k ..\.venv\Scripts\python.exe src\player_main.py
start cmd /k ..\.venv\Scripts\python.exe src\player_main.py &
start cmd /k ..\.venv\Scripts\python.exe src\player_main.py &
start cmd /k ..\.venv\Scripts\python.exe src\player_main.py &
pause