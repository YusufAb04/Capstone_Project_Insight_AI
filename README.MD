# INSIGHT.AI Prototype

INSIGHT.AI is a secure local document intelligence prototype for internal business, operational, and risk analysis.

It allows users to analyse internal documents locally without sending confidential data to external cloud services.

## Core Technologies
- Ollama
- Streamlit
- ChromaDB
- LangChain

## Main Features
- Local document analysis
- Question answering over documents
- Executive summary generation
- Risk and management insight reporting
- Cross-document insights
- Configurable exclusion rules

## Project Structure
- `insight_ai_main.py` – main application
- `insight_ai_backup.py` – backup version
- `docs/` – demo document set
- `requirements.txt` – Python dependencies
- `setup_all.bat` – full setup script
- `install_requirements.bat` – install dependencies only
- `start_insight_ai.bat` – quick launcher

## Setup
1. Install Ollama
2. Pull required models:
   - `ollama pull llama3.2:3b`
   - `ollama pull nomic-embed-text`
3. Run:
   - `setup_all.bat`

## Launch
Double-click:

`start_insight_ai.bat`

Or run manually:

```bash
python -m streamlit run insight_ai_main.py