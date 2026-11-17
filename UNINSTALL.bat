@echo off
setlocal
set "APP_ROOT=%~dp0"
cd /d "%TEMP%"
echo Close Clipboard Float using Quit in its tray menu before continuing.
"%APP_ROOT%runtime\python.exe" "%APP_ROOT%setup_tool.py" --uninstall
if errorlevel 1 (
 pause
 exit /b 1
)
echo Clipboard Float has been uninstalled.
pause
