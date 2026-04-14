@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo   INSIGHT.AI Business Edition - Setup

echo ============================================

echo.
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=python"
    ) else (
        echo [ERROR] Python was not found on this machine.
        echo Please install Python 3.10+ first, then run this file again.
        pause
        exit /b 1
    )
)

echo [1/6] Using Python command: %PY_CMD%

if not exist ".venv\Scripts\python.exe" (
    echo [2/6] Creating virtual environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/6] Virtual environment already exists.
)

echo [3/6] Upgrading pip...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

echo [4/6] Installing required packages...
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install required packages.
    pause
    exit /b 1
)

echo.
set /p INSTALL_OCR=Do you want to install optional OCR packages too? (Y/N): 
if /I "%INSTALL_OCR%"=="Y" (
    echo [5/6] Installing optional OCR Python packages...
    call ".venv\Scripts\python.exe" -m pip install pytesseract pdf2image pillow
    if errorlevel 1 (
        echo [WARNING] Optional OCR Python packages did not install cleanly.
    )
    echo.
    echo NOTE:
    echo - For full OCR fallback, you still need Tesseract OCR installed on Windows.
    echo - You also need Poppler installed for pdf2image.
) else (
    echo [5/6] Skipping optional OCR Python packages.
)

if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "exports" mkdir exports

echo [6/6] Setup finished.
echo.
echo Next step:
echo   Run run_business_edition.bat

echo.
pause
endlocal
