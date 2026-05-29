
# INSIGHT.AI Business Edition

Company-pilot version of INSIGHT.AI with:
- Upload files (TXT, CSV, PDF, DOCX, XLSX)
- Scan local folder recursively
- Batch processing for large datasets
- Re-scan only changed files (hash-based)
- Save metadata + analysis results into SQLite
- OCR fallback for scanned PDFs
- Duplicate file detection & deletion 
- Exclusion keywords to skip matching files during ingestion
- Hybrid BM25 + vector semantic search (ChromaDB)
- AI-powered Q&A via RAG (Ollama + local LLM)
- LLM document enrichment (summaries, risk explanations, executive takeaways)
- Executive dashboard and report export
- Audit logging

## Project structure

- `app.py` — Streamlit UI
- `src/database.py` — SQLite schema and connection
- `src/folder_ingestion.py` — folder scan + hashing
- `src/file_processor.py` — file extraction + OCR fallback + analysis
- `src/batch_processor.py` — batch orchestration and persistence
- `src/duplicate_detector.py` — duplicate file detection
- `src/llm_enricher.py` — Ollama LLM enrichment (summaries, risk, takeaways)
- `src/exporter.py` — reporting and export
- `src/rag/vector_store.py` — ChromaDB vector store + BM25 hybrid search
- `src/rag/chunker.py` — text chunking with section detection
- `src/rag/llm_interface.py` — RAG pipeline (retrieval + Ollama inference)
- Analysis modules: 
  - `src/classifier.py`
  - `src/keyword_extractor.py`
  - `src/risk_engine.py`
  - `src/summarizer.py`
  - `src/text_cleaner.py`


## Run

```bash
setup_all.bat
```

```bash
run.bat
```

## Notes

- Use **Scan Folder and Process Changed Files** for large datasets.
- Re-running the same scan skips unchanged files automatically.
- To change the model copy the model name from Ollama and paste it into the "Ollama model" section on the Operation & Recovery page
