@echo off
python -m pip install pyinstaller
pyinstaller --onefile --windowed --name "RAVEN SAR Mission Control" raven_mission_control.py
pause
