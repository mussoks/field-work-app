@echo off
chcp 65001 >nul
REM 설치 파일 만들기: dist\LearningRecorder-Setup-<버전>.exe
REM 필요: Python 3.10+, Inno Setup 6 (https://jrsoftware.org/isdl.php)
cd /d "%~dp0"
set VERSION=0.2.0

if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || goto :fail

REM uiautomation 의 COM 래퍼를 미리 만들어 두면 실행 파일에 함께 포함된다
python -c "import uiautomation" || goto :fail

pyinstaller --noconfirm --clean --windowed ^
  --name LearningRecorder ^
  --icon src\assets\icon.ico ^
  --add-data "src\assets;assets" ^
  --collect-all imageio_ffmpeg ^
  --collect-all uiautomation ^
  --collect-submodules comtypes ^
  --hidden-import pynput.keyboard._win32 ^
  --hidden-import pynput.mouse._win32 ^
  --exclude-module tkinter ^
  --paths src ^
  src\main.py || goto :fail

if defined SKIP_INSTALLER goto :done
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo.
  echo [안내] Inno Setup 6 이 없어 설치 파일은 만들지 않았어요.
  echo        실행 파일 폴더: dist\LearningRecorder\
  goto :done
)
%ISCC% /DMyAppVersion=%VERSION% installer\LearningRecorder.iss || goto :fail
echo.
echo 완료: dist\LearningRecorder-Setup-%VERSION%.exe

:done
if "%CI%"=="" pause
exit /b 0

:fail
echo 빌드 실패
if "%CI%"=="" pause
exit /b 1
