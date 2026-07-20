@echo off
cd ..
echo "Current working dir is..."
cd

echo "Executing conversion script..."
uv run scripts\build_ui.py

:: echo "Conversion done... Press any key to exit."
:: pause
