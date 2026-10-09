@echo off
rem SS Analyzer launcher: checks Python + deps, runs first-time setup, starts app.
rem Keys + models live in config.json (created on first run — never shipped).
cd /d "%~dp0"
set "PY="
for /f "delims=" %%P in ('where python 2^>nul') do (
    set "PY=%%P"
    goto :havepy
)
echo [SS Analyzer] Python 3.10 or newer is required:
echo   https://www.python.org/downloads/  (tick "Add python.exe to PATH")
pause
exit /b 1
:havepy
"%PY%" -c "import sys; assert sys.version_info>=(3,10)" 2>nul
if errorlevel 1 (
    echo [SS Analyzer] Python 3.10+ required, found older. Update from https://www.python.org/downloads/
    pause
    exit /b 1
)
"%PY%" -c "import PySide6, PIL.Image, requests" 2>nul
if errorlevel 1 (
    echo [SS Analyzer] Installing dependencies, one time only (~150 MB)...
    "%PY%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [SS Analyzer] Install failed. Check your network, then double-click again.
        pause
        exit /b 1
    )
)
set "PYW=%PY:python.exe=pythonw.exe%"
if exist "%PYW%" (
    start "SS Analyzer" "%PYW%" "%~dp0app.py" %*
) else (
    "%PY%" "%~dp0app.py" %*
)
