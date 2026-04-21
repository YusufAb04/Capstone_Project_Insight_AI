@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo   INSIGHT.AI - Setup
echo ============================================
echo.

REM ── IMPORTANT ────────────────────────────────────────────────────────────
echo WARNING: Do NOT place this project inside OneDrive, Google Drive,
echo or any cloud-synced folder. The database and ChromaDB files must
echo remain local to this machine to stay fully offline and to prevent
echo file locking issues during sync.
echo.
pause

REM ── Python check ─────────────────────────────────────────────────────────
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

echo [1/8] Using Python command: %PY_CMD%

REM ── Virtual environment ───────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo [2/8] Creating virtual environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/8] Virtual environment already exists.
)

REM ── pip upgrade ───────────────────────────────────────────────────────────
echo [3/8] Upgrading pip...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

REM ── Core packages ─────────────────────────────────────────────────────────
echo [4/8] Installing core packages...
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install core packages.
    pause
    exit /b 1
)

REM ── Optional OCR ──────────────────────────────────────────────────────────
echo.
set /p INSTALL_OCR=Do you want to install optional OCR packages? (Y/N):
if /I "%INSTALL_OCR%"=="Y" (
    echo [5/8] Installing OCR packages...
    call ".venv\Scripts\python.exe" -m pip install pytesseract pdf2image pillow
    if errorlevel 1 (
        echo [WARNING] OCR packages did not install cleanly.
    )
    echo NOTE: Full OCR also needs native Tesseract OCR and Poppler installed separately.
) else (
    echo [5/8] Skipping OCR packages.
)

REM ── RAG stack ─────────────────────────────────────────────────────────────
echo.
set /p INSTALL_RAG=Do you want to install the AI / RAG stack (Ollama + ChromaDB)? (Y/N):
if /I "%INSTALL_RAG%"=="Y" (
    echo [6/8] Installing RAG packages (this may take a few minutes)...
    call ".venv\Scripts\python.exe" -m pip install chromadb==0.5.23 langchain==0.3.25 langchain-community==0.3.25 langchain-ollama==0.2.5 langchain-text-splitters==0.3.8 sentence-transformers pysqlite3-binary
    if errorlevel 1 (
        echo [WARNING] Some RAG packages did not install cleanly. Check output above.
    )

    echo [7/8] Pre-downloading embedding model (requires internet — only needed once)...
    call ".venv\Scripts\python.exe" -c "from sentence_transformers import SentenceTransformer; print('Downloading all-MiniLM-L6-v2...'); SentenceTransformer('all-MiniLM-L6-v2'); print('Embedding model ready.')"
    if errorlevel 1 (
        echo [WARNING] Embedding model download failed. Ensure internet access and retry.
    )

    echo.
    echo ════════════════════════════════════════════════
    echo   OLLAMA SETUP (required for AI answers)
    echo ════════════════════════════════════════════════
    echo.
    echo  Ollama is NOT a Python package. You must install it separately:
    echo.
    echo  1. Go to: https://ollama.com  and download the Windows installer
    echo  2. Run the installer (it sets up a background service automatically)
    echo  3. Open a NEW terminal window and run:
    echo        ollama pull llama3.2:3b
    echo     This downloads the AI model (~2GB — only needed once)
    echo  4. Ollama runs on http://localhost:11434 — keep it running while using the app
    echo.
    echo  Once Ollama is running, the sidebar in INSIGHT.AI will show a green dot.
    echo ════════════════════════════════════════════════
    echo.
    pause
) else (
    echo [6/8] Skipping RAG stack. The app will use keyword search instead of AI answers.
    echo [7/8] Skipping embedding model download.
)

REM ── Create data directories ────────────────────────────────────────────────
echo [8/8] Creating data directories...
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
echo To start the app, run:  run.bat
echo Or from terminal:       .venv\Scripts\python.exe -m streamlit run app.py
echo.
pause
endlocal
