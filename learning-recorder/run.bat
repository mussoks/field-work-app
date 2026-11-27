@echo off
chcp 65001 >nul
REM 개발용 실행: Python 3.10 이상 필요
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
python src\main.py
