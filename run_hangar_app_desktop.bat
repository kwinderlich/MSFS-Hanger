@echo off
cd /d "%~dp0"
set HANGAR_DESKTOP=1
set HANGAR_DESKTOP_MODE=app
python bootstrap.py
pause
