@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto run
call :candidate py -3.12
call :candidate python
call :candidate python3
call :candidate "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :candidate "%ProgramFiles%\Python312\python.exe"
if not defined PACS_PY goto missing_python
%PACS_PY% -m venv .venv
if errorlevel 1 goto failed
:run
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe launcher.py
if errorlevel 1 goto failed
exit /b 0
:candidate
if defined PACS_PY exit /b 0
"%~1" %~2 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
set PACS_PY="%~1" %~2
exit /b 0
:missing_python
echo Python 3.12 was not found. This batch file is for running source code.
echo For the packaged GUI application, use PACSStatistics.exe instead.
echo Developer setup: https://www.python.org/downloads/windows/
echo Install Python 3.12 and select 'Add python.exe to PATH'.
pause
exit /b 1
:failed
echo Setup or launch failed. Check the error above.
pause
exit /b 1
