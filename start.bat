@echo off
chcp 65001 >nul 2>&1

echo ========================================
echo   Sales Dashboard Launcher
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo [Check] Python found
python --version
echo.

echo [Setup] Checking Python dependencies...
python -c "import fastapi, uvicorn, pymssql" >nul 2>&1
if errorlevel 1 (
    echo [Setup] Missing dependency detected. Installing required packages...
    python -m pip install --disable-pip-version-check -r "%~dp0backend\requirements.txt"
    if errorlevel 1 (
        echo ERROR: Failed to install backend dependencies.
        echo Please check network/proxy settings or install packages manually:
        echo python -m pip install fastapi uvicorn pymssql
        pause
        exit /b 1
    )
) else (
    echo [Setup] Dependencies already available. Skip pip install.
)
echo.

echo [Cleanup] Checking ports 8000 and 8088...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r /c:":8000 " ^| findstr "LISTENING"') do (
    echo [Kill] Free port 8000 PID: %%a...
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r /c:":8088 " ^| findstr "LISTENING"') do (
    echo [Kill] Free port 8088 PID: %%a...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo [Launch] Running run.py...
echo.
python run.py

echo.
pause
