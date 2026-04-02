@echo off
cd /d "%~dp0"
python -m pip install --disable-pip-version-check -r requirements.txt
set HANGAR_DESKTOP=0
python main.py
pause
