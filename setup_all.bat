@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo   INSIGHT.AI - One-Click Setup
echo   (This may take several minutes)
echo ============================================
echo.
echo WARNING: Do NOT place this project inside OneDrive, Google Drive,
echo or any cloud-synced folder. The database and ChromaDB files must
echo remain local to prevent corruption and file locking issues.
echo.
pause

REM ── Python check ─────────────────────────────────────────────────────────
echo [1/7] Checking Python...
echo        Looking for Python 3.12, 3.11, or 3.10 (required for package compatibility)...

set "PY_CMD="

py -3.12 --version >nul 2>nul
if %errorlevel%==0 ( set "PY_CMD=py -3.12" & goto :py_found )

py -3.11 --version >nul 2>nul
if %errorlevel%==0 ( set "PY_CMD=py -3.11" & goto :py_found )

py -3.10 --version >nul 2>nul
if %errorlevel%==0 ( set "PY_CMD=py -3.10" & goto :py_found )

echo.
echo [ERROR] Python 3.10, 3.11, or 3.12 was not found.
echo.
echo This app requires Python 3.10, 3.11, or 3.12.
echo Python 3.13+ is NOT supported yet (packages lack pre-built wheels).
echo.
echo Please download Python 3.12 from:
echo   https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
echo Make sure to tick "Add Python to PATH" during install.
echo Then run this file again.
pause
exit /b 1

:py_found
for /f "tokens=*" %%v in ('%PY_CMD% --version 2^>^&1') do set "PY_VER=%%v"
echo        Python found: %PY_VER%

REM ── 64-bit Python check ───────────────────────────────────────────────────
echo        Checking Python architecture (must be 64-bit)...
for /f %%b in ('%PY_CMD% -c "import sys; print(64 if sys.maxsize > 2**32 else 32)"') do set "PY_BITS=%%b"
if not "!PY_BITS!"=="64" (
    echo.
    echo [ERROR] You have 32-bit Python installed, but this app requires 64-bit Python.
    echo.
    echo Several packages (chromadb, sentence-transformers) only ship pre-built
    echo binaries for 64-bit Windows. On 32-bit Python they try to compile from
    echo source and require a C++ compiler, which is not installed here.
    echo.
    echo Please install the 64-bit version of Python 3.12 from:
    echo   https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    echo Make sure to tick "Add Python to PATH" during install.
    echo Then delete the .venv folder here and run this file again.
    pause
    exit /b 1
)
echo        Architecture: 64-bit OK.

REM ── Bootstrap pip on system Python if missing ─────────────────────────────
echo        Ensuring pip is available...
%PY_CMD% -m pip --version >nul 2>nul
if errorlevel 1 (
    echo        pip not found on system Python. Bootstrapping via ensurepip...
    %PY_CMD% -m ensurepip --upgrade >nul 2>nul
    if errorlevel 1 (
        echo        ensurepip failed. Downloading get-pip.py from PyPA...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%TEMP%\get-pip.py' -UseBasicParsing"
        if errorlevel 1 (
            echo.
            echo [ERROR] Could not download get-pip.py. Check your internet connection.
            pause
            exit /b 1
        )
        %PY_CMD% "%TEMP%\get-pip.py" --quiet
        if errorlevel 1 (
            echo.
            echo [ERROR] Could not install pip. Ask your IT department to install Python with pip enabled.
            pause
            exit /b 1
        )
    )
    echo        pip installed successfully.
) else (
    echo        pip is available.
)

REM ── Virtual environment ───────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo [2/7] Creating virtual environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/7] Virtual environment already exists, skipping.
)

REM ── Bootstrap pip inside the venv if missing ──────────────────────────────
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
    echo        pip missing inside venv. Bootstrapping...
    ".venv\Scripts\python.exe" -m ensurepip --upgrade >nul 2>nul
    if errorlevel 1 (
        echo        ensurepip failed in venv. Trying get-pip.py...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%TEMP%\get-pip.py' -UseBasicParsing"
        ".venv\Scripts\python.exe" "%TEMP%\get-pip.py" --quiet
        if errorlevel 1 (
            echo.
            echo [ERROR] Could not install pip inside the virtual environment.
            pause
            exit /b 1
        )
    )
    echo        pip bootstrapped inside venv.
)

REM ── pip upgrade ───────────────────────────────────────────────────────────
echo [3/7] Upgrading pip...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --prefer-binary
if errorlevel 1 (
    echo [WARNING] pip upgrade failed, continuing anyway.
)

REM ── Pre-install chroma-hnswlib (binary-only, catches C++ issues early) ────
echo [4/7] Installing all required packages...
echo        Step 4a: Pre-installing chroma-hnswlib (binary wheel only, no compilation)...
call ".venv\Scripts\python.exe" -m pip install --only-binary=:all: "chroma-hnswlib>=0.7.3,<0.7.7" --quiet
if errorlevel 1 (
    echo.
    echo [ERROR] Could not find a pre-built binary for chroma-hnswlib.
    echo.
    echo This almost always means you have 32-bit Python installed.
    echo chroma-hnswlib only ships 64-bit binaries for Windows.
    echo.
    echo Fix: Install 64-bit Python 3.12 from:
    echo   https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    echo Tick "Add Python to PATH", delete the .venv folder, then re-run setup.
    pause
    exit /b 1
)
echo        chroma-hnswlib installed (no C++ needed).

REM ── All remaining packages ────────────────────────────────────────────────
echo        Step 4b: Installing remaining packages (this may take several minutes)...
echo.
call ".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed. See output above for details.
    echo.
    echo Common causes:
    echo   - No internet connection
    echo   - University firewall blocking PyPI
    echo   - Disk space too low
    pause
    exit /b 1
)

REM ── Embedding model ───────────────────────────────────────────────────────
echo [5/7] Downloading AI embedding model (one-time, requires internet)...
call ".venv\Scripts\python.exe" -c "from sentence_transformers import SentenceTransformer; print('  Downloading all-MiniLM-L6-v2...'); SentenceTransformer('all-MiniLM-L6-v2'); print('  Embedding model ready.')"
if errorlevel 1 (
    echo [WARNING] Embedding model download failed. Check your internet and re-run setup.
)

REM ── Ollama check and auto-install ─────────────────────────────────────────
echo [6/7] Checking Ollama...

set "OLLAMA_EXE="
where ollama >nul 2>nul
if %errorlevel%==0 (
    set "OLLAMA_EXE=ollama"
    echo        Ollama already installed.
) else if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    echo        Ollama already installed.
)

if "!OLLAMA_EXE!"=="" (
    echo        Ollama not found. Downloading and installing automatically...
    echo        Requires internet connection (~90MB download).
    echo.

    set "OLLAMA_INSTALLER=%TEMP%\OllamaSetup.exe"
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '!OLLAMA_INSTALLER!' -UseBasicParsing"
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not download Ollama installer.
        echo Please check your internet connection, or install manually from https://ollama.com
        echo Then re-run this setup.
        pause
        exit /b 1
    )

    echo        Running Ollama installer...
    start /wait "" "!OLLAMA_INSTALLER!" /S
    if errorlevel 1 (
        echo [WARNING] Ollama installer returned an error. It may still have installed correctly.
    )

    echo        Waiting for Ollama service to start...
    timeout /t 8 /nobreak >nul

    set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"

    if not exist "!OLLAMA_EXE!" (
        echo [WARNING] Ollama executable not found at expected location after install.
        echo You may need to restart your PC and re-run setup, or install manually from https://ollama.com
        set "OLLAMA_EXE="
    ) else (
        echo        Ollama installed successfully.
    )
)

REM ── Pull AI model ─────────────────────────────────────────────────────────
if not "!OLLAMA_EXE!"=="" (
    echo        Pulling AI model llama3.2:3b (~2GB, one-time download)...
    echo        This will take a few minutes depending on your internet speed.
    "!OLLAMA_EXE!" pull llama3.2:3b
    if errorlevel 1 (
        echo [WARNING] Could not pull the AI model right now.
        echo You can run this manually later:  ollama pull llama3.2:3b
    ) else (
        echo        AI model ready.
    )
) else (
    echo [WARNING] Skipping model download - Ollama not found.
    echo Install Ollama from https://ollama.com then run:  ollama pull llama3.2:3b
)

REM ── Create data directories ────────────────────────────────────────────────
echo [7/7] Creating data directories...
if not exist "data" mkdir data
if not exist "data\chromadb" mkdir data\chromadb
if not exist "logs" mkdir logs
if not exist "exports" mkdir exports
if not exist "backups" mkdir backups

echo.
echo ============================================
echo   Setup complete!
echo ============================================
echo.
echo To start the app, double-click:  run.bat
echo.
pause
endlocal
