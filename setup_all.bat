@echo off
title INSIGHT.AI Setup
cd /d %~dp0

echo ========================================
echo       INSIGHT.AI FULL SETUP START
echo ========================================
echo.

echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo [2/6] Creating virtual environment...
if not exist venv (
    python -m venv venv
)

echo [3/6] Activating virtual environment...
call venv\Scripts\activate.bat

echo [4/6] Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

echo [5/6] Checking Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo Ollama not found. Please install Ollama first.
    pause
    exit /b 1
)

echo [6/6] Pulling required models...
ollama pull llama3.2:3b
ollama pull nomic-embed-text

echo.
echo Setup complete.
echo Run the app with:
echo start_insight_ai.bat
echo or
echo python -m streamlit run insight_ai_main.py
echo.
pause