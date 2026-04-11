@echo off
cd /d "%~dp0"
set HANGAR_DESKTOP=0
set HANGAR_HOST=0.0.0.0
python main.py
pause
