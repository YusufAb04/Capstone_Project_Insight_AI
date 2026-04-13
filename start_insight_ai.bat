@echo off
cd /d %~dp0
call venv\Scripts\activate.bat
python -m streamlit run insight_ai_main.py
pause