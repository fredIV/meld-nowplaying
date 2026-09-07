@echo off
setlocal
cd /d "%~dp0"

set PY=py -3
%PY% --version >nul 2>&1 || set PY=python
%PY% --version >nul 2>&1 || (
  echo Python 3 not found. Install it from https://python.org and re-run.
  pause & exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv || (echo venv creation failed & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
)

".venv\Scripts\python.exe" -c "import winrt.windows.media.control, winrt.windows.foundation, websockets" >nul 2>&1
if errorlevel 1 (
  echo Installing dependencies...
  ".venv\Scripts\python.exe" -m pip install --quiet winrt-runtime winrt-Windows.Foundation winrt-Windows.Foundation.Collections winrt-Windows.Media.Control winrt-Windows.Storage.Streams websockets || (
    echo Dependency install failed. & pause & exit /b 1
  )
)

".venv\Scripts\python.exe" server.py
pause
