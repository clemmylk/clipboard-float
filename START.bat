@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\pythonw.exe" (
 echo Extract the entire Windows-x64 ZIP first. Python is included there.
 pause
 exit /b 1
)
start "" "%~dp0runtime\pythonw.exe" "%~dp0clipboard_history.py"
