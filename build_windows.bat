@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
python -m unittest -v
if errorlevel 1 goto failed
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PACSStatistics --add-data "templates;templates" --collect-all pywinauto --collect-all comtypes --collect-all tzdata launcher.py
if errorlevel 1 goto failed
echo GUI executable created: dist\PACSStatistics.exe
pause
exit /b 0
:failed
echo Build failed. Check the error above.
pause
exit /b 1
