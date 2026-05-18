@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
 
title INSIGHT.AI - Smart Setup
 
echo ============================================
echo   INSIGHT.AI - Smart Setup
echo   Python + Packages + Ollama
echo   C++ Build Tools only if needed
echo ============================================
echo.
echo This setup will try to install Python packages first.
echo Microsoft C++ Build Tools will only be installed if pip fails
echo while building chroma-hnswlib / ChromaDB dependencies.
echo.
echo WARNING: Do NOT place this project inside OneDrive, Google Drive,
echo or any cloud-synced folder. ChromaDB files should remain local.
echo.
pause
 
REM -------------------------------------------------------------------------
REM Python check / auto-install. Prefer Python 3.11 for package compatibility.
REM -------------------------------------------------------------------------
echo.
echo [1/7] Checking Python 3.10 / 3.11 / 3.12...
set "PY_CMD="
 
py -3.11 --version >nul 2>nul
if "%errorlevel%"=="0" (
    set "PY_CMD=py -3.11"
    goto :python_ready
)
 
py -3.12 --version >nul 2>nul
if "%errorlevel%"=="0" (
    set "PY_CMD=py -3.12"
    goto :python_ready
)
 
py -3.10 --version >nul 2>nul
if "%errorlevel%"=="0" (
    set "PY_CMD=py -3.10"
    goto :python_ready
)
 
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :python_ready
)
 
if exist "%ProgramFiles%\Python311\python.exe" (
    set PY_CMD="%ProgramFiles%\Python311\python.exe"
    goto :python_ready
)
 
echo        Python 3.10/3.11/3.12 not found.
echo        Downloading Python 3.11.9 automatically...
set "PY_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%PY_INSTALLER%' -UseBasicParsing"
if errorlevel 1 (
    echo.
    echo [ERROR] Could not download Python installer.
    echo Check your internet connection and run setup_all.bat again.
    pause
    exit /b 1
)
 
echo        Installing Python 3.11.9 for current user...
start /wait "" "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 SimpleInstall=1
if errorlevel 1 (
    echo.
    echo [ERROR] Python installation failed.
    pause
    exit /b 1
)
 
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    py -3.11 --version >nul 2>nul
    if "%errorlevel%"=="0" set "PY_CMD=py -3.11"
)
 
:python_ready
if "!PY_CMD!"=="" (
    echo [ERROR] Python still could not be found after installation.
    echo Restart Windows and run setup_all.bat again.
    pause
    exit /b 1
)
echo        Python ready: !PY_CMD!
!PY_CMD! --version
 
REM -------------------------------------------------------------------------
REM Virtual environment
REM -------------------------------------------------------------------------
echo.
echo [2/7] Creating virtual environment...
if exist ".venv\Scripts\python.exe" (
    echo        Existing .venv found. Removing it to avoid package conflicts...
    rmdir /s /q ".venv"
)
 
!PY_CMD! -m venv .venv
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
 
echo        Virtual environment ready.
 
REM -------------------------------------------------------------------------
REM pip upgrade
REM -------------------------------------------------------------------------
echo.
echo [3/7] Upgrading pip/setuptools/wheel...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel --quiet
if errorlevel 1 (
    echo [WARNING] pip upgrade failed, continuing anyway.
)
 
REM -------------------------------------------------------------------------
REM Python packages - first try without C++ Build Tools.
REM -------------------------------------------------------------------------
echo.
echo [4/7] Installing Python packages...
echo        First attempt: prefer prebuilt wheels, no C++ install yet.
call ".venv\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 (
    echo.
    echo [WARNING] Package installation failed.
    echo This project uses ChromaDB, which depends on chroma-hnswlib.
    echo On some Windows/Python setups, chroma-hnswlib must be compiled,
    echo and that requires Microsoft C++ Build Tools.
    echo.
    choice /M "Install Microsoft C++ Build Tools automatically and retry"
    if errorlevel 2 (
        echo.
        echo Setup stopped. You can still install manually:
        echo https://visualstudio.microsoft.com/visual-cpp-build-tools/
        pause
        exit /b 1
    )
    call :install_cpp_build_tools
    if errorlevel 1 exit /b 1
    echo.
    echo Retrying Python package installation after C++ Build Tools...
    call ".venv\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Package installation still failed.
        echo Try restarting Windows, then run setup_all.bat again.
        pause
        exit /b 1
    )
)
echo        Python packages installed.
 
REM -------------------------------------------------------------------------
REM Sentence-transformers embedding model
REM -------------------------------------------------------------------------
echo.
echo [5/7] Downloading local embedding model...
call ".venv\Scripts\python.exe" -c "from sentence_transformers import SentenceTransformer; print('Downloading all-MiniLM-L6-v2...'); SentenceTransformer('all-MiniLM-L6-v2'); print('Embedding model ready.')"
if errorlevel 1 (
    echo [WARNING] Embedding model download failed.
    echo Check internet and run setup_all.bat again later.
)
 
REM -------------------------------------------------------------------------
REM Ollama install / model pull
REM -------------------------------------------------------------------------
echo.
echo [6/7] Checking Ollama...
set "OLLAMA_EXE="
where ollama >nul 2>nul
if "%errorlevel%"=="0" set "OLLAMA_EXE=ollama"
if "!OLLAMA_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if "!OLLAMA_EXE!"=="" if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
 
if "!OLLAMA_EXE!"=="" (
    echo        Ollama not found. Downloading Ollama automatically...
    set "OLLAMA_INSTALLER=%TEMP%\OllamaSetup.exe"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '!OLLAMA_INSTALLER!' -UseBasicParsing"
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not download Ollama installer.
        echo Install manually from https://ollama.com and run setup_all.bat again.
        pause
        exit /b 1
    )
 
    echo        Installing Ollama...
    start /wait "" "!OLLAMA_INSTALLER!" /S
    timeout /t 8 /nobreak >nul
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    if "!OLLAMA_EXE!"=="" if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
)
 
if "!OLLAMA_EXE!"=="" (
    echo [WARNING] Ollama was not found after install.
    echo Install manually from https://ollama.com then run:
    echo ollama pull llama3.2:3b
) else (
    echo        Ollama ready: !OLLAMA_EXE!
    echo        Pulling llama3.2:3b model. This can take several minutes...
    "!OLLAMA_EXE!" pull llama3.2:3b
    if errorlevel 1 (
        echo [WARNING] Could not pull llama3.2:3b now.
        echo Run manually later: ollama pull llama3.2:3b
    )
)
 
REM -------------------------------------------------------------------------
REM Create data directories
REM -------------------------------------------------------------------------
echo.
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
echo To start the app, double-click: run.bat
echo.
pause
endlocal
exit /b 0
 
REM -------------------------------------------------------------------------
REM Function: Install Microsoft C++ Build Tools.
REM -------------------------------------------------------------------------
:install_cpp_build_tools
net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo.
    echo Administrator permission is required to install C++ Build Tools.
    echo Windows will ask for permission. Click YES.
    echo After the C++ installer finishes, run setup_all.bat again if this window closes.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 1
)
 
set "VS_OK=0"
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "!VSWHERE!" (
    for /f "usebackq tokens=*" %%i in (`"!VSWHERE!" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul`) do (
        if not "%%i"=="" set "VS_OK=1"
    )
)
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC" set "VS_OK=1"
if exist "%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC" set "VS_OK=1"
 
if "!VS_OK!"=="1" (
    echo        Microsoft C++ Build Tools already installed.
    exit /b 0
)
 
echo        Downloading Microsoft Visual Studio Build Tools...
set "VS_INSTALLER=%TEMP%\vs_BuildTools.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vs_BuildTools.exe' -OutFile '%VS_INSTALLER%' -UseBasicParsing"
if errorlevel 1 (
    echo.
    echo [ERROR] Could not download Microsoft C++ Build Tools.
    echo Manual download: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1
)
 
echo        Installing C++ Build Tools workload...
echo        This can take 20-45 minutes. Do NOT close this window.
start /wait "" "%VS_INSTALLER%" --quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended
set "VS_EXIT=%errorlevel%"
if not "!VS_EXIT!"=="0" if not "!VS_EXIT!"=="3010" (
    echo.
    echo [ERROR] C++ Build Tools installation failed. Exit code: !VS_EXIT!
    pause
    exit /b 1
)
 
echo        C++ Build Tools installed.
exit /b 0