@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run: run.ps1 -Setup
  exit /b 1
)
call .venv\Scripts\activate.bat
set PYTHONIOENCODING=utf-8
python web_app.py
