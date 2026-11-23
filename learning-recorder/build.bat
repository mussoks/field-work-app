@echo off
chcp 65001 >nul
REM 단일 실행 파일(dist\LearningRecorder.exe) 빌드
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name LearningRecorder ^
  --collect-all imageio_ffmpeg ^
  --hidden-import pynput.keyboard._win32 ^
  --hidden-import pynput.mouse._win32 ^
  --paths src ^
  src\main.py
echo.
echo 완료: dist\LearningRecorder.exe
pause
