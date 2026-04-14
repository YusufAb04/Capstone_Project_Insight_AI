@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo   INSIGHT.AI Business Edition - Launch

echo ============================================

echo.
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run setup_all.bat first.
    pause
    exit /b 1
)

if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "exports" mkdir exports

echo Starting Streamlit app...
call ".venv\Scripts\python.exe" -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo [ERROR] The app stopped with an error.
    echo Check that setup_all.bat completed successfully.
    pause
    exit /b 1
)

endlocal
