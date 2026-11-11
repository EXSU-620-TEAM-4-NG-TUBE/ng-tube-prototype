@echo off
setlocal
set "BENCH_PYTHON=%LOCALAPPDATA%\Programs\Thonny\python.exe"
if not exist "%BENCH_PYTHON%" set "BENCH_PYTHON=python"
"%BENCH_PYTHON%" -c "import serial" >nul 2>&1
if errorlevel 1 (
 echo Python with pyserial is required. Install requirements.txt using your Python environment.
 pause
 exit /b 1
)
"%BENCH_PYTHON%" "%~dp0browser_monitor\service.py"
pause
