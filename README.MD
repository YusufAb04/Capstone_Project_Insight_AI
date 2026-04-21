
# INSIGHT.AI Business Edition

Company-pilot version of INSIGHT.AI with:
- upload files
- scan folder recursive
- batch processing for large datasets
- save metadata + results into SQLite
- re-scan only changed files
- error logs
- OCR fallback hooks for scanned PDFs
- executive dashboard and report export

## Project structure

- `app.py` — Streamlit UI
- `src/database.py` — SQLite schema and connection
- `src/folder_ingestion.py` — folder scan + hashing
- `src/file_processor.py` — file extraction + OCR fallback + analysis
- `src/batch_processor.py` — batch orchestration and persistence
- `src/exporter.py` — reporting
- existing analysis modules reused:
  - `src/classifier.py`
  - `src/keyword_extractor.py`
  - `src/risk_engine.py`
  - `src/summarizer.py`
  - `src/text_cleaner.py`

## Install

```bash
pip install streamlit pandas PyPDF2 python-docx
```

Optional for OCR fallback on scanned PDFs:

```bash
pip install pytesseract pdf2image pillow
```

You also need:
- Tesseract OCR installed on the machine
- Poppler installed for `pdf2image`

If OCR dependencies are missing, normal PDF text extraction still works.

## Run

```bash
streamlit run app.py
```

## Notes

- Set the SQLite database path in the sidebar.
- Use **Scan Folder and Process Changed Files** for large datasets.
- Re-running the same scan skips unchanged files automatically.
