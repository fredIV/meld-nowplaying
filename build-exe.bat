@echo off
setlocal
cd /d "%~dp0"

set PY=py -3
%PY% --version >nul 2>&1 || set PY=python
%PY% --version >nul 2>&1 || (echo Python 3 not found. & pause & exit /b 1)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv || (echo venv creation failed & pause & exit /b 1)
)
set VPY=.venv\Scripts\python.exe

echo Installing build dependencies...
"%VPY%" -m pip install --quiet --upgrade pip
"%VPY%" -m pip install --quiet winrt-runtime winrt-Windows.Foundation winrt-Windows.Foundation.Collections winrt-Windows.Media.Control winrt-Windows.Storage.Streams websockets pyinstaller || (
  echo Dependency install failed. & pause & exit /b 1
)

echo Building meld-nowplaying.exe ...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile ^
  --name meld-nowplaying ^
  --add-data "overlay.html;." ^
  --add-data "settings.html;." ^
  --collect-all winrt ^
  --hidden-import websockets ^
  --exclude-module tkinter --exclude-module unittest --exclude-module pydoc ^
  --exclude-module doctest --exclude-module lib2to3 --exclude-module pdb ^
  --exclude-module xmlrpc --exclude-module sqlite3 --exclude-module distutils ^
  server.py || (echo Build failed. & pause & exit /b 1)

echo.
echo Done. The executable is in the dist folder:
echo   %CD%\dist\meld-nowplaying.exe
echo.
pause
