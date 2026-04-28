# LLM Analysis Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four rule-based text fields (`summary`, `document_type`, `risk_explanation`, `management_takeaway`) with LLM-generated plain-English outputs using the already-running Ollama instance, while keeping `risk_score`, `risk_label`, and `keywords` rule-based.

**Architecture:** A new pure module `src/llm_enricher.py` makes a single Ollama call with a delimiter-based prompt and parses the four fields. `file_processor.py` accepts an optional `llm` argument and merges enriched fields after the rule-based pass. `batch_processor.py` creates one LLM instance before each ingestion loop and adds a new `enrich_existing_with_llm()` function for batch back-fill. A new `llm_enriched` flag on the `files` table tracks enrichment state. The `app.py` UI adds an enrich button in Operations and a ✨ badge on enriched files in the File Explorer.

**Tech Stack:** `langchain_ollama.ChatOllama` (already installed), SQLite `_ensure_column` migration pattern, Streamlit `st.progress`, pytest + `unittest.mock`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/llm_enricher.py` | Pure enrichment function and response parser |
| Create | `tests/test_llm_enricher.py` | Unit tests for parser and enricher |
| Create | `tests/__init__.py` | Empty file to make tests a package |
| Modify | `src/database.py` line 189 | Add `llm_enriched INTEGER DEFAULT 0` migration |
| Modify | `src/file_processor.py` lines 239-320 | Add `llm` param; merge enrichment into result |
| Modify | `src/batch_processor.py` lines 13-19, 78-120, 191-257, 260-307 | LLM imports, `upsert_file_record`, both ingestion functions, new `enrich_existing_with_llm` |
| Modify | `app.py` lines 18-27, 311-347, 723-741, 1060-1101 | Import, `load_records`, file list badge, enrich button |

---

### Task 1: Create `src/llm_enricher.py` with unit tests

**Files:**
- Create: `src/llm_enricher.py`
- Create: `tests/__init__.py`
- Create: `tests/test_llm_enricher.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/__init__.py` (empty file) and `tests/test_llm_enricher.py`:

```python
# tests/test_llm_enricher.py
from unittest.mock import MagicMock

import pytest

from src.llm_enricher import _parse_response, enrich_with_llm

_VALID_RAW = (
    "SUMMARY: This is a test document.\n"
    "TYPE: Contract\n"
    "RISK: There is moderate liability risk.\n"
    "TAKEAWAY: Legal review recommended."
)


def test_parse_response_returns_all_four_fields():
    result = _parse_response(_VALID_RAW)
    assert result is not None
    assert result["summary"] == "This is a test document."
    assert result["document_type"] == "Contract"
    assert result["risk_explanation"] == "There is moderate liability risk."
    assert result["management_takeaway"] == "Legal review recommended."


def test_parse_response_missing_field_returns_none():
    raw = "SUMMARY: Summary only.\nTYPE: Contract\nRISK: Some risk."
    assert _parse_response(raw) is None


def test_parse_response_empty_returns_none():
    assert _parse_response("") is None


def test_parse_response_extra_lines_ignored():
    raw = "Preamble text\n" + _VALID_RAW + "\nTrailing text"
    result = _parse_response(raw)
    assert result is not None
    assert result["document_type"] == "Contract"


def _make_llm(raw_content: str):
    mock_response = MagicMock()
    mock_response.content = raw_content
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


def test_enrich_with_llm_success():
    llm = _make_llm(_VALID_RAW)
    result = enrich_with_llm("some document content", "Medium", llm)
    assert result is not None
    assert result["document_type"] == "Contract"
    assert result["summary"] == "This is a test document."


def test_enrich_with_llm_malformed_response_returns_none():
    llm = _make_llm("SUMMARY: Only one field.")
    result = enrich_with_llm("content", "Low", llm)
    assert result is None


def test_enrich_with_llm_exception_returns_none():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("Ollama timeout")
    result = enrich_with_llm("content", "High", mock_llm)
    assert result is None


def test_enrich_with_llm_truncates_long_content():
    long_content = " ".join(["word"] * 2000)
    llm = _make_llm(_VALID_RAW)
    enrich_with_llm(long_content, "Low", llm)
    called_prompt = str(llm.invoke.call_args[0][0])
    # Truncated at 1500 words — count of "word" in the prompt must be ≤ 1500
    assert called_prompt.count("word") <= 1500
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd "C:\Projects\INSIGHT_AI - Copy"
.venv\Scripts\activate
pip install pytest
pytest tests/test_llm_enricher.py -v
```

Expected: `ImportError: cannot import name '_parse_response' from 'src.llm_enricher'` (module doesn't exist yet).

- [ ] **Step 3: Create `src/llm_enricher.py`**

```python
from __future__ import annotations

_MAX_WORDS = 1500

_PROMPT_TEMPLATE = (
    "Analyse this document and respond in exactly this format — no extra text:\n"
    "SUMMARY: <2-3 sentence plain-English summary>\n"
    "TYPE: <one of: Invoice / Contract / Policy / Meeting Notes / HR Document"
    " / Financial Record / Report / Security Document / General Business File>\n"
    "RISK: <1-2 sentences explaining the main risks,"
    ' or "No significant risks identified." if low risk>\n'
    "TAKEAWAY: <1-2 sentences for an executive>\n\n"
    "Risk level assessed by rules: {risk_label}\n\n"
    "Document (may be truncated):\n{text}"
)

_PREFIX_TO_KEY = {
    "SUMMARY:": "summary",
    "TYPE:": "document_type",
    "RISK:": "risk_explanation",
    "TAKEAWAY:": "management_takeaway",
}

_REQUIRED_KEYS = {"summary", "document_type", "risk_explanation", "management_takeaway"}


def enrich_with_llm(content: str, risk_label: str, llm) -> dict | None:
    words = content.split()
    text = " ".join(words[:_MAX_WORDS]) if len(words) > _MAX_WORDS else content
    prompt = _PROMPT_TEMPLATE.format(risk_label=risk_label, text=text)
    try:
        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
    except Exception:
        return None
    return _parse_response(raw)


def _parse_response(raw: str) -> dict | None:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        for prefix, key in _PREFIX_TO_KEY.items():
            if line.startswith(prefix):
                result[key] = line[len(prefix):].strip()
                break
    if result.keys() == _REQUIRED_KEYS:
        return result
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_llm_enricher.py -v
```

Expected: 8 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/llm_enricher.py tests/__init__.py tests/test_llm_enricher.py
git commit -m "feat: add llm_enricher module with parser and unit tests"
```

---

### Task 2: Add `llm_enriched` column migration in `src/database.py`

**Files:**
- Modify: `src/database.py` lines 183-189
- Modify: `tests/test_llm_enricher.py` (append new test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_llm_enricher.py`:

```python
import sqlite3, tempfile, os

def test_init_database_adds_llm_enriched_column():
    from src.database import init_database
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(files)").fetchall()]
        conn.close()
        assert "llm_enriched" in cols
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_llm_enricher.py::test_init_database_adds_llm_enriched_column -v
```

Expected: FAILED — `AssertionError: assert 'llm_enriched' in [...]`

- [ ] **Step 3: Add migration line to `src/database.py`**

Find the migrations block (around line 183-189) which currently ends with:
```python
    _ensure_column(cur, "files", "chunk_count", "chunk_count INTEGER DEFAULT 0")
```

Add one line immediately after it:
```python
    _ensure_column(cur, "files", "llm_enriched", "llm_enriched INTEGER DEFAULT 0")
```

The full block after the edit:
```python
    # Additive migrations — safe to run on existing databases
    _ensure_column(cur, "analysis_results", "content_text", "content_text TEXT")
    _ensure_column(cur, "analysis_results", "risk_explanation", "risk_explanation TEXT")

    # RAG sync tracking columns
    _ensure_column(cur, "files", "chroma_synced", "chroma_synced INTEGER DEFAULT 0")
    _ensure_column(cur, "files", "chunk_count", "chunk_count INTEGER DEFAULT 0")

    # LLM enrichment flag
    _ensure_column(cur, "files", "llm_enriched", "llm_enriched INTEGER DEFAULT 0")
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_llm_enricher.py::test_init_database_adds_llm_enriched_column -v
```

Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/database.py tests/test_llm_enricher.py
git commit -m "feat: add llm_enriched column migration to files table"
```

---

### Task 3: Add `llm` param to `src/file_processor.py`

**Files:**
- Modify: `src/file_processor.py` lines 239-320

- [ ] **Step 1: Write the failing test**

Append to `tests/test_llm_enricher.py`:

```python
def test_process_file_bytes_enriches_when_llm_provided():
    from src.file_processor import process_file_bytes
    llm = _make_llm(_VALID_RAW)
    content = b"This is a sample contract document with some text content for testing."
    result = process_file_bytes("test.txt", content, llm=llm)
    assert result["llm_enriched"] == 1
    assert result["document_type"] == "Contract"
    assert result["summary"] == "This is a test document."


def test_process_file_bytes_skips_enrichment_when_llm_none():
    from src.file_processor import process_file_bytes
    content = b"This is a sample document."
    result = process_file_bytes("test.txt", content, llm=None)
    assert result["llm_enriched"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_llm_enricher.py::test_process_file_bytes_enriches_when_llm_provided tests/test_llm_enricher.py::test_process_file_bytes_skips_enrichment_when_llm_none -v
```

Expected: FAILED — `TypeError: process_file_bytes() got an unexpected keyword argument 'llm'`

- [ ] **Step 3: Update `process_file_bytes` in `src/file_processor.py`**

Change the signature (line 239) from:
```python
def process_file_bytes(
    filename: str,
    data: bytes,
    mode: str = "Premium",
    ocr_config: Optional[dict] = None,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
```
to:
```python
def process_file_bytes(
    filename: str,
    data: bytes,
    mode: str = "Premium",
    ocr_config: Optional[dict] = None,
    file_path: Optional[str] = None,
    llm=None,
) -> Dict[str, Any]:
```

- [ ] **Step 4: Add enrichment logic inside `process_file_bytes`**

After the line `mode_result = apply_mode_processing(analysis_text, mode)` (currently around line 278), add:

```python
    _llm_enriched = 0
    if llm is not None:
        from src.llm_enricher import enrich_with_llm
        enriched = enrich_with_llm(analysis_text, mode_result["risk_label"], llm)
        if enriched:
            mode_result.update(enriched)
            _llm_enriched = 1
```

Then in the `return` dict (add `"llm_enriched": _llm_enriched` as a new key):

```python
    return {
        "filename": filename,
        "file_path": file_path or f"uploaded://{filename}",
        "filetype": extension.upper(),
        "mode": mode_result["mode"],
        "content": analysis_text,
        "raw_content": raw_content,
        "cleaned_content": cleaned_content,
        "char_count": len(analysis_text),
        "word_count": len(analysis_text.split()) if analysis_text else 0,
        "document_type": mode_result["document_type"],
        "summary": mode_result["summary"],
        "keywords": mode_result["keywords"],
        "risk_score": mode_result["risk_score"],
        "risk_label": mode_result["risk_label"],
        "risk_categories": mode_result["risk_categories"],
        "flagged_phrases": mode_result["flagged_phrases"],
        "management_takeaway": mode_result["management_takeaway"],
        "risk_explanation": mode_result["risk_explanation"],
        "ocr_used": ocr_used,
        "llm_enriched": _llm_enriched,
    }
```

- [ ] **Step 5: Update `process_file_path` and `process_uploaded_file` to accept and pass `llm`**

Change `process_file_path` (around line 303):
```python
def process_file_path(file_path: str, mode: str = "Premium", ocr_config: Optional[dict] = None, llm=None) -> Dict[str, Any]:
    path = Path(file_path)
    data = path.read_bytes()
    return process_file_bytes(path.name, data, mode=mode, ocr_config=ocr_config, file_path=file_path, llm=llm)
```

Change `process_uploaded_file` (around line 309):
```python
def process_uploaded_file(uploaded_file, mode: str = "Premium", ocr_config: Optional[dict] = None, llm=None) -> Dict[str, Any]:
    return process_file_bytes(
        uploaded_file.name,
        uploaded_file.getvalue(),
        mode=mode,
        ocr_config=ocr_config,
        file_path=f"uploaded://{uploaded_file.name}",
        llm=llm,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```
pytest tests/test_llm_enricher.py -v
```

Expected: all tests PASSED.

- [ ] **Step 7: Commit**

```bash
git add src/file_processor.py tests/test_llm_enricher.py
git commit -m "feat: add optional llm param to process_file_bytes for LLM enrichment"
```

---

### Task 4: Update `src/batch_processor.py` for auto-enrichment and batch back-fill

**Files:**
- Modify: `src/batch_processor.py` lines 13-19, 78-121, 191-257, 260-307
- Add new function `enrich_existing_with_llm`

- [ ] **Step 1: Write the failing test for `enrich_existing_with_llm`**

Append to `tests/test_llm_enricher.py`:

```python
import json, tempfile, os

def test_enrich_existing_with_llm_updates_zero_enriched_files():
    from src.database import init_database, get_connection
    from src.batch_processor import enrich_existing_with_llm

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        init_database(db_path)

        conn = get_connection(db_path)
        conn.execute(
            "INSERT INTO files (file_path, file_name, extension, file_size, modified_time, "
            "file_hash, status, ocr_used, last_processed_at, llm_enriched) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("uploaded://doc.txt", "doc.txt", "TXT", 100, 0.0, "abc", "processed", 0, "2026-01-01", 0),
        )
        conn.commit()
        file_id = conn.execute("SELECT id FROM files WHERE file_path = 'uploaded://doc.txt'").fetchone()[0]
        conn.execute(
            "INSERT INTO analysis_results (file_id, document_type, summary, keywords_json, "
            "risk_score, risk_label, risk_categories_json, flagged_phrases_json, "
            "management_takeaway, word_count, char_count, mode, content_text, risk_explanation) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_id, "Report", "Old summary.", "[]", 10, "Low", "[]", "[]",
             "Old takeaway.", 5, 30, "Premium", "Sample document text.", "Old explanation."),
        )
        conn.commit()
        conn.close()

        llm = _make_llm(_VALID_RAW)
        count = enrich_existing_with_llm(db_path, llm)

        assert count == 1
        conn2 = get_connection(db_path)
        row = conn2.execute(
            "SELECT summary, document_type FROM analysis_results WHERE file_id = ?", (file_id,)
        ).fetchone()
        enriched_flag = conn2.execute(
            "SELECT llm_enriched FROM files WHERE id = ?", (file_id,)
        ).fetchone()[0]
        conn2.close()

        assert row["summary"] == "This is a test document."
        assert row["document_type"] == "Contract"
        assert enriched_flag == 1


def test_enrich_existing_with_llm_skips_already_enriched():
    from src.database import init_database, get_connection
    from src.batch_processor import enrich_existing_with_llm

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        init_database(db_path)

        conn = get_connection(db_path)
        conn.execute(
            "INSERT INTO files (file_path, file_name, extension, file_size, modified_time, "
            "file_hash, status, ocr_used, last_processed_at, llm_enriched) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("uploaded://doc2.txt", "doc2.txt", "TXT", 100, 0.0, "def", "processed", 0, "2026-01-01", 1),
        )
        conn.commit()
        conn.close()

        llm = _make_llm(_VALID_RAW)
        count = enrich_existing_with_llm(db_path, llm)
        assert count == 0
        assert not llm.invoke.called
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_llm_enricher.py::test_enrich_existing_with_llm_updates_zero_enriched_files tests/test_llm_enricher.py::test_enrich_existing_with_llm_skips_already_enriched -v
```

Expected: FAILED — `ImportError: cannot import name 'enrich_existing_with_llm' from 'src.batch_processor'`

- [ ] **Step 3: Add LLM imports to `src/batch_processor.py`**

After the existing RAG try/except block (lines 13-19), add:

```python
# LLM enrichment (requires RAG stack)
try:
    from src.rag.llm_interface import check_ollama_status as _check_ollama_status
    from src.rag.llm_interface import get_llm as _llm_factory
    from src.llm_enricher import enrich_with_llm
    _ENRICHMENT_AVAILABLE = True
except ImportError:
    _ENRICHMENT_AVAILABLE = False
```

- [ ] **Step 4: Add `_get_ingestion_llm` helper to `src/batch_processor.py`**

Add after the existing `_load_chroma_dir` function (around line 36):

```python
def _get_ingestion_llm(db_path: str):
    """Return a ChatOllama instance if Ollama is reachable, else None."""
    if not _ENRICHMENT_AVAILABLE:
        return None
    base_url = get_setting(db_path, "ollama_base_url", "http://localhost:11434") or "http://localhost:11434"
    model = get_setting(db_path, "ollama_model", "llama3.2:3b") or "llama3.2:3b"
    if not _check_ollama_status(base_url):
        return None
    try:
        return _llm_factory(model_name=model, base_url=base_url)
    except Exception:
        return None
```

- [ ] **Step 5: Add `llm_enriched` param to `upsert_file_record`**

Change the function signature from:
```python
def upsert_file_record(
    conn,
    *,
    file_path: str,
    file_name: str,
    extension: str,
    file_size: int,
    modified_time: float,
    file_hash: str,
    status: str,
    ocr_used: bool,
    chroma_synced: int = 0,
    chunk_count: int = 0,
) -> int:
```
to:
```python
def upsert_file_record(
    conn,
    *,
    file_path: str,
    file_name: str,
    extension: str,
    file_size: int,
    modified_time: float,
    file_hash: str,
    status: str,
    ocr_used: bool,
    chroma_synced: int = 0,
    chunk_count: int = 0,
    llm_enriched: int = 0,
) -> int:
```

Change the UPDATE SQL inside `upsert_file_record` from:
```python
        cur.execute(
            """
            UPDATE files
            SET file_name = ?, extension = ?, file_size = ?, modified_time = ?, file_hash = ?,
                status = ?, ocr_used = ?, last_processed_at = ?, chroma_synced = ?, chunk_count = ?
            WHERE id = ?
            """,
            (file_name, extension, file_size, modified_time, file_hash, status,
             int(bool(ocr_used)), now_str(), chroma_synced, chunk_count, file_id),
        )
```
to:
```python
        cur.execute(
            """
            UPDATE files
            SET file_name = ?, extension = ?, file_size = ?, modified_time = ?, file_hash = ?,
                status = ?, ocr_used = ?, last_processed_at = ?, chroma_synced = ?, chunk_count = ?,
                llm_enriched = ?
            WHERE id = ?
            """,
            (file_name, extension, file_size, modified_time, file_hash, status,
             int(bool(ocr_used)), now_str(), chroma_synced, chunk_count, llm_enriched, file_id),
        )
```

Change the INSERT SQL inside `upsert_file_record` from:
```python
        cur.execute(
            """
            INSERT INTO files
            (file_path, file_name, extension, file_size, modified_time, file_hash,
             status, ocr_used, last_processed_at, chroma_synced, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_path, file_name, extension, file_size, modified_time, file_hash,
             status, int(bool(ocr_used)), now_str(), chroma_synced, chunk_count),
        )
```
to:
```python
        cur.execute(
            """
            INSERT INTO files
            (file_path, file_name, extension, file_size, modified_time, file_hash,
             status, ocr_used, last_processed_at, chroma_synced, chunk_count, llm_enriched)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_path, file_name, extension, file_size, modified_time, file_hash,
             status, int(bool(ocr_used)), now_str(), chroma_synced, chunk_count, llm_enriched),
        )
```

- [ ] **Step 6: Update `process_folder_to_db` to create and pass the LLM**

In `process_folder_to_db`, after `ocr_config = load_ocr_config(db_path)`, add:
```python
    llm = _get_ingestion_llm(db_path)
```

Change the `result = process_file_path(...)` call to:
```python
            result = process_file_path(file_path, mode=mode, ocr_config=ocr_config, llm=llm)
```

Change the `upsert_file_record(...)` call (success path) to include `llm_enriched`:
```python
            file_id = upsert_file_record(
                conn,
                file_path=file_path,
                file_name=meta["file_name"],
                extension=meta["extension"],
                file_size=meta["file_size"],
                modified_time=meta["modified_time"],
                file_hash=file_hash,
                status="processed",
                ocr_used=result.get("ocr_used", False),
                chroma_synced=chroma_synced,
                chunk_count=chunk_count,
                llm_enriched=result.get("llm_enriched", 0),
            )
```

- [ ] **Step 7: Update `process_uploaded_files_to_db` to create and pass the LLM**

In `process_uploaded_files_to_db`, after `ocr_config = load_ocr_config(db_path)`, add:
```python
    llm = _get_ingestion_llm(db_path)
```

Change the `result = process_uploaded_file(...)` call to:
```python
            result = process_uploaded_file(uploaded_file, mode=mode, ocr_config=ocr_config, llm=llm)
```

Change the `upsert_file_record(...)` call (success path) to include `llm_enriched`:
```python
            file_id = upsert_file_record(
                conn,
                file_path=pseudo_path,
                file_name=uploaded_file.name,
                extension=result.get("filetype", ""),
                file_size=len(uploaded_file.getvalue()),
                modified_time=0.0,
                file_hash="uploaded-session",
                status="processed",
                ocr_used=result.get("ocr_used", False),
                chroma_synced=chroma_synced,
                chunk_count=chunk_count,
                llm_enriched=result.get("llm_enriched", 0),
            )
```

- [ ] **Step 8: Add `enrich_existing_with_llm` function to `src/batch_processor.py`**

Add after `sync_missing_to_chroma` (around line 388):

```python
def enrich_existing_with_llm(db_path: str, llm, progress_callback: ProgressCallback = None) -> int:
    """Enrich all processed files that have not yet been LLM-enriched.

    Updates summary, document_type, risk_explanation, management_takeaway in
    analysis_results and sets files.llm_enriched = 1 on success.
    Returns count of successfully enriched files.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT f.id, f.file_name, a.content_text, a.risk_label
        FROM files f
        JOIN analysis_results a ON a.file_id = f.id
        WHERE f.llm_enriched = 0 AND f.status = 'processed'
        """
    )
    pending = cur.fetchall()
    conn.close()

    total = len(pending)
    enriched_count = 0

    for idx, row in enumerate(pending, start=1):
        file_id = row[0]
        file_name = row[1]
        content_text = row[2]
        risk_label = row[3]
        if content_text and risk_label:
            enriched = enrich_with_llm(content_text, risk_label, llm)
            if enriched:
                conn2 = get_connection(db_path)
                conn2.execute(
                    """
                    UPDATE analysis_results
                    SET summary = ?, document_type = ?, risk_explanation = ?, management_takeaway = ?
                    WHERE file_id = ?
                    """,
                    (
                        enriched["summary"],
                        enriched["document_type"],
                        enriched["risk_explanation"],
                        enriched["management_takeaway"],
                        file_id,
                    ),
                )
                conn2.execute("UPDATE files SET llm_enriched = 1 WHERE id = ?", (file_id,))
                conn2.commit()
                conn2.close()
                enriched_count += 1
        if progress_callback:
            progress_callback(idx, total, file_name)

    return enriched_count
```

- [ ] **Step 9: Run tests to verify they pass**

```
pytest tests/test_llm_enricher.py -v
```

Expected: all tests PASSED.

- [ ] **Step 10: Commit**

```bash
git add src/batch_processor.py tests/test_llm_enricher.py
git commit -m "feat: auto-enrich on ingestion and add enrich_existing_with_llm batch function"
```

---

### Task 5: Update `app.py` — Enrich button and ✨ badge

**Files:**
- Modify: `app.py` lines 18-27 (imports from batch_processor)
- Modify: `app.py` lines 311-347 (load_records)
- Modify: `app.py` lines 733-741 (Browse Files file rows)
- Modify: `app.py` lines 1060-1101 (Operations AI/RAG Settings tab)

- [ ] **Step 1: Add `enrich_existing_with_llm` to the `batch_processor` import block**

Change (lines 18-27):
```python
from src.batch_processor import (
    process_uploaded_files_to_db,
    process_folder_to_db,
    get_run_stats,
    create_schedule,
    list_schedules,
    update_schedule_status,
    run_due_schedules,
    _CHROMA_AVAILABLE,
)
```
to:
```python
from src.batch_processor import (
    process_uploaded_files_to_db,
    process_folder_to_db,
    get_run_stats,
    create_schedule,
    list_schedules,
    update_schedule_status,
    run_due_schedules,
    enrich_existing_with_llm,
    _CHROMA_AVAILABLE,
)
```

- [ ] **Step 2: Add `f.llm_enriched` to `load_records()`**

In `load_records` (around line 326), change the SELECT SQL from:
```python
    select_sql = f"""
        SELECT
            f.file_path, f.file_name, f.extension, f.file_size, f.modified_time, f.file_hash,
            f.status, f.ocr_used, f.last_processed_at,
            a.document_type, a.summary, a.keywords_json, a.risk_score, a.risk_label,
            a.risk_categories_json, a.flagged_phrases_json, a.management_takeaway,
            a.word_count, a.char_count, a.mode, {', '.join(optional_cols)}
        FROM files f
        LEFT JOIN analysis_results a ON a.file_id = f.id
        ORDER BY f.last_processed_at DESC, f.file_name ASC
        LIMIT ?
    """
```
to:
```python
    select_sql = f"""
        SELECT
            f.file_path, f.file_name, f.extension, f.file_size, f.modified_time, f.file_hash,
            f.status, f.ocr_used, f.last_processed_at, f.llm_enriched,
            a.document_type, a.summary, a.keywords_json, a.risk_score, a.risk_label,
            a.risk_categories_json, a.flagged_phrases_json, a.management_takeaway,
            a.word_count, a.char_count, a.mode, {', '.join(optional_cols)}
        FROM files f
        LEFT JOIN analysis_results a ON a.file_id = f.id
        ORDER BY f.last_processed_at DESC, f.file_name ASC
        LIMIT ?
    """
```

- [ ] **Step 3: Add ✨ badge in Browse Files file rows**

In `render_file_explorer`, inside the file rows loop (around line 737), change:
```python
            c1.write(fname[:48] + "…" if len(fname) > 48 else fname)
```
to:
```python
            badge = "✨ " if row.get("llm_enriched") == 1 else ""
            display_name = badge + (fname[:46] + "…" if len(fname) > 46 else fname)
            c1.write(display_name)
```

- [ ] **Step 4: Add Enrich button in Operations → AI/RAG Settings tab**

In `render_operations`, inside `with tabs[4]:`, after the "Save RAG settings" block (after line 1091) and before the divider + Ollama setup instructions, add:

```python
        st.divider()
        st.markdown("### Batch AI Enrichment")
        st.write("Generate LLM summaries and risk analysis for all previously processed files.")

        try:
            _conn_tmp = get_connection(st.session_state.db_path)
            _unenriched = _conn_tmp.execute(
                "SELECT COUNT(*) FROM files WHERE llm_enriched = 0 AND status = 'processed'"
            ).fetchone()[0]
            _conn_tmp.close()
        except Exception:
            _unenriched = 0

        st.caption(f"{_unenriched} file(s) not yet enriched with AI.")

        _enrich_disabled = not health.get("ollama_reachable") or not _RAG_IMPORTS_OK
        if st.button("Enrich existing files with AI", disabled=_enrich_disabled):
            _llm = get_llm(model_name=_ollama_model())
            _progress_bar = st.progress(0.0)
            _status_text = st.empty()

            def _enrich_cb(done: int, total: int, fname: str) -> None:
                _progress_bar.progress(done / total if total else 1.0)
                _status_text.text(f"[{done}/{total}] {fname}")

            _count = enrich_existing_with_llm(
                st.session_state.db_path, _llm, progress_callback=_enrich_cb
            )
            _progress_bar.progress(1.0)
            _status_text.empty()
            st.success(f"Enriched {_count} file(s) with AI analysis.")
        elif _enrich_disabled and not health.get("ollama_reachable"):
            st.caption("Start Ollama to enable enrichment.")
```

- [ ] **Step 5: Run the app and verify end-to-end**

```
cd "C:\Projects\INSIGHT_AI - Copy"
.venv\Scripts\activate
streamlit run app.py
```

Verify:
1. Operations → AI/RAG Settings tab shows "Batch AI Enrichment" section with file count
2. With Ollama running: clicking "Enrich existing files with AI" shows progress bar then success message
3. File Explorer → Browse Files shows ✨ prefix on enriched files
4. New files uploaded while Ollama is online have ✨ badge immediately after ingestion
5. New files uploaded while Ollama is offline have no ✨ badge (rule-based fields used)

- [ ] **Step 6: Run all tests**

```
pytest tests/ -v
```

Expected: all tests PASSED.

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "feat: add LLM enrich button in Operations and AI badge in File Explorer"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|---|---|
| `enrich_with_llm(content, risk_label, llm) -> dict \| None` | Task 1 |
| Truncate content to ~1500 words | Task 1 |
| Single LLM call with delimiter prompt | Task 1 |
| Parse four fields; return None if any missing | Task 1 |
| `llm_enriched INTEGER DEFAULT 0` on `files` table | Task 2 |
| `process_file_bytes` optional `llm` param | Task 3 |
| Merge enriched fields; keep rule-based score/label/keywords | Task 3 |
| Create LLM once before ingestion loop | Task 4 |
| `llm=None` fallback if Ollama unreachable | Task 4 |
| `enrich_existing_with_llm(db_path, llm, progress_callback) -> int` | Task 4 |
| Queries `files JOIN analysis_results WHERE llm_enriched=0 AND status='processed'` | Task 4 |
| Sets `llm_enriched=1` on success | Task 4 |
| Skips already-enriched files on re-run | Task 4 |
| "Enrich existing files with AI" button with progress bar | Task 5 |
| Shows count of enriched files on completion | Task 5 |
| ✨ badge for `llm_enriched=1` in Browse Files | Task 5 |
| No new Python packages | All tasks (uses existing langchain_ollama) |
| `llm_enricher.py` has no Streamlit imports | Task 1 (pure module) |

**Type consistency check:** `enrich_with_llm` is referenced in Task 1 (definition), Task 3 (imported lazily in file_processor), Task 4 (imported at module top). Signature is `enrich_with_llm(content: str, risk_label: str, llm) -> dict | None` — consistent throughout.

**Placeholder scan:** None found — all steps contain complete code.
