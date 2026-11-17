@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\python.exe" goto missing
"%~dp0runtime\python.exe" "%~dp0setup_tool.py"
if errorlevel 1 goto failed
echo.
echo Setup complete. Press Tab + V or use Clipboard Float on your desktop.
pause
exit /b 0
:missing
echo Extract ALL files from the Windows-x64 setup ZIP first.
:failed
echo Setup did not finish. Read the message above.
pause
exit /b 1
