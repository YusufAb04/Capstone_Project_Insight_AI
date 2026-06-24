
# INSIGHT.AI Business Edition

## Overview
INSIGHT.AI is a secure local/offline document intelligence application. It is designed to help users analyse business documents without uploading confidential data to external cloud AI services.
The application allows users to upload files, scan local folders, exclude unnecessary or sensitive files, index document content, ask questions over the indexed documents, view an executive dashboard and inspect logs or processing results.


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


## To use the application, simply run the following batch files

```bash
setup_all.bat
```

```bash
run.bat
```

<img width="1919" height="1029" alt="Image" src="https://github.com/user-attachments/assets/e776ac53-43b9-445d-a5d7-89f06078362d" />

<img width="1919" height="1031" alt="Image" src="https://github.com/user-attachments/assets/e7dbbf21-6588-47ab-9349-2b5349b2084e" />

<img width="1919" height="1029" alt="Image" src="https://github.com/user-attachments/assets/e46c3ad7-db57-47c9-800a-d565eb034a84" />

<img width="1919" height="1025" alt="Image" src="https://github.com/user-attachments/assets/3e0ba9cc-fb82-4c4b-80ac-9e930a86fce1" />

<img width="1913" height="1004" alt="Image" src="https://github.com/user-attachments/assets/bb41049d-5b47-4542-91eb-0390fbdfa713" />





## Notes

- Use **Scan Folder and Process Changed Files** for large datasets.
- Re-running the same scan skips unchanged files automatically.
- To change the model copy the model name from Ollama and paste it into the "Ollama model" section on the Operation & Recovery page
