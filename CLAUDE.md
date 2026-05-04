# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Running the App

```bash
# Activate the virtual environment first
.venv/Scripts/activate   # Windows bash

# Run the Streamlit app
streamlit run app.py
```

On Windows you can also double-click `run.bat`.

## Installing Dependencies

```bash
# Activate the virtual environment first
.venv/Scripts/activate   # Windows bash

pip install -r requirements.txt
```

For optional OCR support:
```bash
pip install pytesseract pdf2image pillow
```

Ollama must be installed separately from https://ollama.com (Windows installer).
After installing, pull the model: `ollama pull llama3.2:3b`

## Important: Do NOT put this project in OneDrive or any cloud folder

The `data/chromadb/` directory contains binary vector store files that OneDrive will lock and corrupt during sync. The SQLite database also contains indexed document content that should never leave the device. Always run this project from a local path like `C:\Projects\INSIGHT_AI\`.

## Architecture Overview

Local-first, fully offline document intelligence tool with RAG-powered Q&A.

### Tech Stack
- **Streamlit** — UI framework
- **ChromaDB** — local vector store for document chunk embeddings
- **Ollama** — local LLM runner (llama3.2:3b recommended for 8GB RAM)
- **LangChain** — RAG chain orchestration (LCEL)
- **sentence-transformers** — local embedding model (all-MiniLM-L6-v2)
- **SQLite** — metadata, analysis results, settings, logs
- **scikit-learn** — TF-IDF fallback when Ollama is offline

### Request / Data Flow

```
User action (Streamlit UI)
  └─▶ app.py  (renders pages, calls src modules)
        ├─▶ src/batch_processor.py   (orchestrates runs, skips unchanged files)
        │     ├─▶ src/folder_ingestion.py   (scans directories, SHA-256 hashes)
        │     ├─▶ src/file_processor.py     (text extraction + rule-based analysis)
        │     └─▶ src/rag/chunker.py        (splits content into overlapping chunks)
        │           └─▶ src/rag/vector_store.py  (upserts chunks into ChromaDB)
        ├─▶ src/rag/llm_interface.py   (Ollama LLM + LCEL RAG chain)
        ├─▶ src/rag/health.py          (component health checks)
        ├─▶ src/duplicate_detector.py  (SHA-256 duplicate detection)
        └─▶ src/database.py    (SQLite schema, settings, backup/restore)
```

### Analysis Pipeline (src/file_processor.py)

1. **Text extraction** — TXT, CSV, PDF (PyPDF2 + optional OCR), DOCX
2. **Cleaning** — `text_cleaner.clean_extracted_text`
3. **Rule-based analysis** — classifier, summarizer, keyword extractor, risk engine
4. **Chunking + embedding** — `chunker.chunk_text` → `vector_store.upsert_document`

### RAG Q&A Pipeline (src/rag/)

```
User question
  └─▶ vector_store.similarity_search()  (ChromaDB cosine similarity, top-4 chunks)
        └─▶ llm_interface.ask_with_rag()
              ├─▶ Format retrieved chunks as context
              ├─▶ ChatOllama (llama3.2:3b, num_ctx=4096, temperature=0.1)
              └─▶ Return answer + source file citations
```

When Ollama is offline, the app falls back to TF-IDF cosine similarity on stored summaries.

### RAG Modules (src/rag/)

| Module | Purpose |
|---|---|
| `__init__.py` | pysqlite3 patch for Windows SQLite compatibility |
| `chunker.py` | RecursiveCharacterTextSplitter (chunk_size=500, overlap=75) |
| `vector_store.py` | ChromaDB PersistentClient singleton, cosine distance collection |
| `llm_interface.py` | ChatOllama wrapper, LCEL chain, `ask_with_rag()` |
| `health.py` | Health checks for all RAG components |

### Rule-Based Analysis Modules (src/)

| Module | Approach |
|---|---|
| `classifier.py` | Keyword-count per document type |
| `summarizer.py` | Sentence scoring via word frequency + IMPORTANT_TERMS boost |
| `keyword_extractor.py` | Token frequency + BUSINESS_PRIORITY boost |
| `risk_engine.py` | Weighted category keyword hits; score capped at 85 |
| `duplicate_detector.py` | SHA-256 hash comparison against files table |

### Database Schema (src/database.py)

Key tables:
- `files` — one row per file; includes `chroma_synced` and `chunk_count` for RAG sync tracking
- `analysis_results` — rule-based analysis output (keywords, risk, summary, etc.)
- `processing_runs` — one row per batch run
- `scan_schedules` — scheduled folder scans
- `system_settings` — key/value store (OCR config + RAG config: model, chroma_dir)
- `audit_logs`, `error_logs`, `validation_runs`, `validation_details`

### Streamlit UI Pages

| Page | Key function |
|---|---|
| Home | `render_home()` — multi-turn chat interface |
| Ingestion Hub | `render_ingestion()` — upload or folder scan |
| Executive Dashboard | `render_dashboard()` — risk distribution + top-risk cards |
| File Explorer | `render_file_explorer()` — filterable table + duplicate detection |
| Ask Questions | `render_questions()` — RAG Q&A with TF-IDF fallback |
| Operations & Recovery | `render_operations()` — schedules, backup, OCR, validation, RAG settings |
| Reports and Logs | `render_reports()` — TXT/JSON export, run history, logs |

### Model Recommendations (8GB RAM)

| Component | Recommended | RAM usage |
|---|---|---|
| Embedding | all-MiniLM-L6-v2 | ~280MB |
| LLM | llama3.2:3b (Q4_K_M via Ollama) | ~2.1GB |

### Supported File Types

`.txt`, `.csv`, `.pdf`, `.docx`
