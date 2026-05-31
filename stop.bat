@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

echo ========================================
echo   Sales Dashboard Stopper
echo ========================================
echo.

set "PIDS="

for %%P in (8000 8088) do (
    echo [Check] Port %%P...
    for /f "tokens=5" %%A in ('netstat -aon ^| findstr /r /c:":%%P " ^| findstr "LISTENING"') do (
        set "PID=%%A"
        echo !PIDS! | findstr /c:" !PID! " >nul
        if errorlevel 1 (
            set "PIDS=!PIDS! !PID! "
            echo [Kill] PID !PID! on port %%P
            taskkill /F /PID !PID! >nul 2>&1
            if errorlevel 1 (
                echo [Warn] Failed to stop PID !PID!
            ) else (
                echo [OK] Stopped PID !PID!
            )
        ) else (
            echo [Skip] PID !PID! already handled
        )
    )
)

echo.
if "%PIDS%"=="" (
    echo [Done] No dashboard process is listening on ports 8000 or 8088.
) else (
    echo [Done] Released dashboard ports: 8000, 8088.
)

endlocal
