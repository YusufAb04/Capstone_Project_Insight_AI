@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title INSIGHT.AI - One-Click Setup

REM ── Self-spawning wrapper ─────────────────────────────────────────────────
REM  The PARENT spawns a CHILD (cmd /c) to run the actual setup.
REM  No matter what the child does, the PARENT always shows the result + pause.
REM  _INSIGHT_INNER is inherited by the child so it knows it is the child.
if defined _INSIGHT_INNER goto :setup_body

set "_INSIGHT_INNER=1"
cmd /c ""%~f0""
set "_R=%errorlevel%"

REM Flush keyboard buffer so any key pressed during install doesn't auto-dismiss
powershell -NoProfile -Command "try { $Host.UI.RawUI.FlushInputBuffer() } catch {}" >nul 2>nul

echo.
echo.
if "%_R%"=="0" (
    echo ============================================
    echo   Setup complete!
    echo ============================================
    echo.
    echo To start the app, double-click:  run.bat
) else (
    echo ============================================
    echo   Setup stopped  --  exit code %_R%
    echo ============================================
    echo.
    echo Scroll up to read the error above.
    echo Fix it, then run setup_all.bat again.
)
echo.
pause
endlocal
exit /b %_R%

REM ════════════════════════════════════════════════════════════════════════════
:setup_body
REM  Everything below is the actual setup. It runs as the CHILD process.
REM  Use "exit /b 1" freely -- the parent wrapper always catches it.
REM ════════════════════════════════════════════════════════════════════════════

echo ============================================
echo   INSIGHT.AI - One-Click Setup
echo   Python + Packages + Ollama
echo   (This may take several minutes)
echo ============================================
echo.
echo WARNING: Do NOT place this project inside OneDrive, Google Drive,
echo or any cloud-synced folder. The database and ChromaDB files must
echo remain local to prevent corruption and file locking issues.
echo.
pause

REM ── [1/6] Python ─────────────────────────────────────────────────────────
echo.
echo [1/6] Checking Python 3.10 / 3.11 / 3.12...
echo        (Python 3.13+ is NOT yet supported)

set "PY_CMD="

py -3.11 --version >nul 2>nul
if "%errorlevel%"=="0" ( set "PY_CMD=py -3.11" & goto :py_found )

py -3.12 --version >nul 2>nul
if "%errorlevel%"=="0" ( set "PY_CMD=py -3.12" & goto :py_found )

py -3.10 --version >nul 2>nul
if "%errorlevel%"=="0" ( set "PY_CMD=py -3.10" & goto :py_found )

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :py_found
)
if exist "%ProgramFiles%\Python311\python.exe" (
    set "PY_CMD=%ProgramFiles%\Python311\python.exe"
    goto :py_found
)

echo        Not found. Downloading Python 3.11.9 automatically (~25 MB)...
set "PY_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%PY_INSTALLER%' -UseBasicParsing"
if errorlevel 1 (
    echo.
    echo [ERROR] Could not download Python. Check your internet connection.
    echo Download manually: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo Tick "Add Python to PATH", then run setup_all.bat again.
    exit /b 1
)

echo        Installing Python 3.11.9...
start /wait "" "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 SimpleInstall=1
if errorlevel 1 (
    echo [ERROR] Python installation failed.
    exit /b 1
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    py -3.11 --version >nul 2>nul
    if "%errorlevel%"=="0" set "PY_CMD=py -3.11"
)

:py_found
if "!PY_CMD!"=="" (
    echo [ERROR] Python still not found after install. Restart Windows and try again.
    exit /b 1
)
for /f "tokens=*" %%v in ('!PY_CMD! --version 2^>^&1') do echo        Found: %%v

REM 64-bit check
for /f %%b in ('!PY_CMD! -c "import sys; print(64 if sys.maxsize > 2**32 else 32)"') do set "PY_BITS=%%b"
if not "!PY_BITS!"=="64" (
    echo.
    echo [ERROR] 32-bit Python detected. This app needs 64-bit Python.
    echo Install from: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    exit /b 1
)
echo        64-bit OK.

REM ── [2/6] Virtual environment ─────────────────────────────────────────────
echo.
echo [2/6] Setting up virtual environment...
if exist ".venv\Scripts\python.exe" (
    echo        Removing old .venv to avoid stale conflicts...
    rmdir /s /q ".venv"
)
!PY_CMD! -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    exit /b 1
)
echo        Virtual environment ready.

REM ── [3/6] Upgrade pip ─────────────────────────────────────────────────────
echo.
echo [3/6] Upgrading pip, setuptools, wheel...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel --quiet
if errorlevel 1 echo [WARNING] pip upgrade failed, continuing anyway.

REM ── [4/6] Install packages ────────────────────────────────────────────────
echo.
echo [4/6] Installing Python packages (may take several minutes)...
call ".venv\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed.
    echo Common causes:
    echo   - No internet connection
    echo   - Firewall blocking PyPI
    echo   - Disk space too low
    echo.
    echo If the error mentions "chroma-hnswlib" or "build wheel":
    echo   Make sure you have 64-bit Python 3.10, 3.11, or 3.12.
    exit /b 1
)
echo        Packages installed.

REM ── [5/6] Embedding model ─────────────────────────────────────────────────
echo.
echo [5/6] Downloading AI embedding model (one-time, ~90 MB)...
call ".venv\Scripts\python.exe" -c "from sentence_transformers import SentenceTransformer; print('  Downloading all-MiniLM-L6-v2...'); SentenceTransformer('all-MiniLM-L6-v2'); print('  Done.')"
if errorlevel 1 echo [WARNING] Embedding model download failed. Run setup_all.bat again when connected.

REM ── [6/6] Ollama ─────────────────────────────────────────────────────────
echo.
echo [6/6] Checking Ollama...

set "OLLAMA_EXE="

where ollama >nul 2>nul
if not errorlevel 1 set "OLLAMA_EXE=ollama"

if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"

if defined OLLAMA_EXE goto :ollama_pull

REM Ollama not found -- download and install
echo        Not found. Downloading Ollama automatically (~90 MB)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '$env:TEMP\OllamaSetup.exe' -UseBasicParsing"
if errorlevel 1 (
    echo [ERROR] Could not download Ollama. Install manually from https://ollama.com
    exit /b 1
)
echo        Installing Ollama...
start /wait "" "%TEMP%\OllamaSetup.exe" /S
timeout /t 8 /nobreak >nul

if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"

if not defined OLLAMA_EXE (
    echo [WARNING] Ollama not found after install. Install from https://ollama.com
    echo           Then run:  ollama pull llama3.2:3b
    goto :ollama_done
)

:ollama_pull
echo        Ollama ready: !OLLAMA_EXE!
echo        Pulling llama3.2:3b model (2 GB, one-time download)...
"!OLLAMA_EXE!" pull llama3.2:3b
if errorlevel 1 echo [WARNING] Model pull failed. Run manually:  ollama pull llama3.2:3b
if not errorlevel 1 echo        AI model ready.

:ollama_done

REM ── Data directories ──────────────────────────────────────────────────────
if not exist "data"           mkdir data
if not exist "data\chromadb"  mkdir data\chromadb
if not exist "logs"           mkdir logs
if not exist "exports"        mkdir exports
if not exist "backups"        mkdir backups

exit /b 0
