# Cross-Device Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make INSIGHT_AI give consistent RAG answers across all devices after fresh ingestion by pinning dependencies, validating setup on first run, verifying chunks land in ChromaDB, and surfacing actionable error messages.

**Architecture:** Four independent layers — dependency pinning prevents version drift; a health check module detects broken components before ingestion; post-ingestion verification catches silent ChromaDB write failures; structured error types in the RAG pipeline replace the single generic fallback message with specific, actionable diagnostics.

**Tech Stack:** Python, pytest, unittest.mock, sentence-transformers, chromadb, streamlit, requests

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `requirements.txt` | Exact pinned versions for all dependencies |
| Create | `src/health_check.py` | Four component check functions + `run_all_checks` |
| Create | `tests/test_health_check.py` | Unit tests for health_check.py |
| Create | `tests/test_chunk_verification.py` | Unit tests for verify_chunk_counts |
| Create | `tests/test_llm_interface_errors.py` | Unit tests for error_type in ask_with_rag |
| Modify | `src/batch_processor.py` | Add `verify_chunk_counts()`, import `get_collection` |
| Modify | `src/rag/llm_interface.py` | Add `_run_chain` helper, return `error_type` from `ask_with_rag` |
| Modify | `app.py` | Health check tab, ingestion verification UI, honest error messages |
| Modify | `CLAUDE.md` | Update install instructions to reference requirements.txt |

---

## Task 1: Pin requirements.txt

**Files:**
- Create: `requirements.txt`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Create requirements.txt**

```text
# requirements.txt — pinned for cross-device consistency
streamlit==1.56.0
pandas==3.0.2
PyPDF2==3.0.1
python-docx==1.2.0
scikit-learn==1.8.0
requests==2.33.1
chromadb==0.5.23
langchain==0.3.25
langchain-community==0.3.25
langchain-ollama==0.2.3
langchain-text-splitters==0.3.8
sentence-transformers==5.4.1
pysqlite3-binary
```

- [ ] **Step 2: Update CLAUDE.md install section**

Replace the existing "Installing Dependencies" section with:

```markdown
## Installing Dependencies

```bash
pip install -r requirements.txt
```

For optional OCR support:
```bash
pip install pytesseract pdf2image pillow
```

Ollama must be installed separately from https://ollama.com (Windows installer).
After installing, pull the model: `ollama pull llama3.2:3b`
```

- [ ] **Step 3: Verify install works**

Run: `.venv/Scripts/pip install -r requirements.txt --dry-run`
Expected: no conflicts, all packages resolve to pinned versions.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt CLAUDE.md
git commit -m "feat: pin all dependencies in requirements.txt for cross-device consistency"
```

---

## Task 2: Health Check Module

**Files:**
- Create: `src/health_check.py`
- Create: `tests/test_health_check.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_health_check.py`:

```python
import pytest
import requests
from unittest.mock import patch, MagicMock
from src.health_check import (
    check_embedding_model,
    check_ollama,
    check_disk,
    CheckResult,
)


def test_check_embedding_model_ok():
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.0] * 384
    with patch("src.health_check._SentenceTransformer", return_value=mock_model):
        result = check_embedding_model()
    assert result.status == "ok"


def test_check_embedding_model_wrong_dims():
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.0] * 100
    with patch("src.health_check._SentenceTransformer", return_value=mock_model):
        result = check_embedding_model()
    assert result.status == "fail"
    assert "384" in result.message


def test_check_embedding_model_import_error():
    with patch("src.health_check._SentenceTransformer", None):
        result = check_embedding_model()
    assert result.status == "fail"
    assert "pip install" in result.fix


def test_check_ollama_ok():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
    with patch("src.health_check.requests.get", return_value=mock_resp):
        result = check_ollama("http://localhost:11434", "llama3.2:3b")
    assert result.status == "ok"


def test_check_ollama_model_not_pulled():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": []}
    with patch("src.health_check.requests.get", return_value=mock_resp):
        result = check_ollama("http://localhost:11434", "llama3.2:3b")
    assert result.status == "warn"
    assert "ollama pull" in result.fix


def test_check_ollama_unreachable():
    with patch("src.health_check.requests.get", side_effect=requests.exceptions.ConnectionError()):
        result = check_ollama("http://localhost:11434", "llama3.2:3b")
    assert result.status == "fail"
    assert "ollama serve" in result.fix


def test_check_disk_writable(tmp_path):
    result = check_disk(str(tmp_path / "data"))
    assert result.status == "ok"


def test_check_disk_cloud_sync_onedrive(tmp_path):
    cloud_path = str(tmp_path) + "/OneDrive/MyProject/data"
    result = check_disk(cloud_path)
    assert result.status == "warn"
    assert "cloud" in result.fix.lower() or "onedrive" in result.fix.lower()


def test_check_disk_cloud_sync_google_drive(tmp_path):
    cloud_path = str(tmp_path) + "/Google Drive/MyProject/data"
    result = check_disk(cloud_path)
    assert result.status == "warn"
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `.venv/Scripts/pytest tests/test_health_check.py -v`
Expected: `ModuleNotFoundError: No module named 'src.health_check'`

- [ ] **Step 3: Create src/health_check.py**

```python
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Literal

import requests

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer
except ImportError:
    _SentenceTransformer = None

try:
    import chromadb as _chromadb
except ImportError:
    _chromadb = None

Status = Literal["ok", "warn", "fail"]

_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_EXPECTED_DIMS = 384
_CLOUD_SYNC_MARKERS = ("onedrive", "google drive", "dropbox", "iclouddrive")


@dataclass
class CheckResult:
    name: str
    status: Status
    message: str
    fix: str = ""


def check_embedding_model() -> CheckResult:
    if _SentenceTransformer is None:
        return CheckResult(
            name="Embedding model",
            status="fail",
            message="sentence-transformers is not installed.",
            fix="Run: pip install sentence-transformers==5.4.1",
        )
    try:
        model = _SentenceTransformer(_EMBEDDING_MODEL)
        embedding = model.encode("test sentence")
        if len(embedding) != _EXPECTED_DIMS:
            return CheckResult(
                name="Embedding model",
                status="fail",
                message=f"Expected {_EXPECTED_DIMS} dimensions, got {len(embedding)}. Model may be corrupted.",
                fix="Delete the cached model folder in ~/.cache/huggingface and restart the app to re-download.",
            )
        return CheckResult(
            name="Embedding model",
            status="ok",
            message=f"{_EMBEDDING_MODEL} loaded — producing valid {_EXPECTED_DIMS}-dim embeddings.",
        )
    except Exception as exc:
        return CheckResult(
            name="Embedding model",
            status="fail",
            message=f"Failed to load: {exc}",
            fix="Run: pip install sentence-transformers==5.4.1",
        )


def check_chromadb(persist_dir: str) -> CheckResult:
    if _chromadb is None:
        return CheckResult(
            name="ChromaDB vector store",
            status="fail",
            message="chromadb is not installed.",
            fix="Run: pip install chromadb==0.5.23",
        )
    try:
        import src.rag  # ensure pysqlite3 patch is applied before chromadb opens any db
        with tempfile.TemporaryDirectory() as tmp:
            client = _chromadb.PersistentClient(path=tmp)
            col = client.get_or_create_collection("_health_test")
            col.upsert(ids=["probe"], documents=["health check"], metadatas=[{"source": "health"}])
            result = col.get(ids=["probe"])
            if not result["ids"]:
                raise RuntimeError("Write/read cycle produced no results")
        chunk_count = 0
        try:
            real_client = _chromadb.PersistentClient(path=persist_dir)
            real_col = real_client.get_or_create_collection("insight_documents")
            chunk_count = real_col.count()
        except Exception:
            pass
        return CheckResult(
            name="ChromaDB vector store",
            status="ok",
            message=f"Writable. pysqlite3 patch active. {chunk_count} chunks currently indexed.",
        )
    except Exception as exc:
        return CheckResult(
            name="ChromaDB vector store",
            status="fail",
            message=f"ChromaDB error: {exc}",
            fix="Run: pip install chromadb==0.5.23 pysqlite3-binary. Ensure the data/ folder is writable.",
        )


def check_ollama(base_url: str = "http://localhost:11434", model: str = "llama3.2:3b") -> CheckResult:
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=3)
        if resp.status_code != 200:
            return CheckResult(
                name="Ollama LLM",
                status="fail",
                message=f"Ollama responded with HTTP {resp.status_code}.",
                fix="Open a terminal and run: ollama serve",
            )
        models = [m["name"] for m in resp.json().get("models", [])]
        model_base = model.split(":")[0]
        if not any(model_base in m for m in models):
            return CheckResult(
                name="Ollama LLM",
                status="warn",
                message=f"Ollama is running but model '{model}' is not pulled.",
                fix=f"Open a terminal and run: ollama pull {model}",
            )
        return CheckResult(
            name="Ollama LLM",
            status="ok",
            message=f"Ollama running. Model '{model}' is available.",
        )
    except requests.exceptions.ConnectionError:
        return CheckResult(
            name="Ollama LLM",
            status="fail",
            message="Ollama is not running.",
            fix="Open a terminal and run: ollama serve  (or launch the Ollama desktop app)",
        )
    except Exception as exc:
        return CheckResult(
            name="Ollama LLM",
            status="fail",
            message=f"Could not reach Ollama: {exc}",
            fix="Open a terminal and run: ollama serve",
        )


def check_disk(data_dir: str) -> CheckResult:
    resolved = os.path.abspath(data_dir).lower()
    for marker in _CLOUD_SYNC_MARKERS:
        if marker in resolved:
            return CheckResult(
                name="Disk / database",
                status="warn",
                message=f"Project appears to be inside a cloud-sync folder ({marker.title()}).",
                fix="Move the project to a local path like C:\\Projects\\INSIGHT_AI. Cloud sync can lock and corrupt ChromaDB files.",
            )
    try:
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, "_write_test.tmp")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return CheckResult(
            name="Disk / database",
            status="ok",
            message=f"Data directory is writable: {data_dir}",
        )
    except Exception as exc:
        return CheckResult(
            name="Disk / database",
            status="fail",
            message=f"Cannot write to data directory: {exc}",
            fix="Check folder permissions or move the project to a local path.",
        )


def run_all_checks(persist_dir: str, base_url: str, model: str, data_dir: str) -> list[CheckResult]:
    return [
        check_embedding_model(),
        check_chromadb(persist_dir),
        check_ollama(base_url, model),
        check_disk(data_dir),
    ]
```

- [ ] **Step 4: Run tests — confirm they pass**

Run: `.venv/Scripts/pytest tests/test_health_check.py -v`
Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/health_check.py tests/test_health_check.py
git commit -m "feat: add health check module with embedding, chromadb, ollama, and disk checks"
```

---

## Task 3: Health Check UI in Operations

**Files:**
- Modify: `app.py` — `render_operations()` (line 859), `render_questions()` (line 804)

- [ ] **Step 1: Add health check imports to app.py**

At the top of `app.py`, after the existing RAG imports block (around line 47), add:

```python
try:
    from src.health_check import run_all_checks, CheckResult
    _HEALTH_CHECK_AVAILABLE = True
except ImportError:
    _HEALTH_CHECK_AVAILABLE = False
```

- [ ] **Step 2: Add "Setup Health Check" tab to render_operations()**

In `render_operations()` at line 862, change the `st.tabs(...)` call from:

```python
tabs = st.tabs(["Scheduled scans", "Backup & recovery", "OCR diagnostics", "Validation metrics", "AI / RAG Settings"])
```

to:

```python
tabs = st.tabs(["Scheduled scans", "Backup & recovery", "OCR diagnostics", "Validation metrics", "AI / RAG Settings", "Setup Health Check"])
```

Then add a new `with tabs[5]:` block at the end of `render_operations()`, before the closing of the function:

```python
    with tabs[5]:
        st.markdown("### Setup Health Check")
        st.write("Verify all components are working correctly before ingesting documents on a new device.")

        run_btn = st.button("▶ Run checks", type="primary")
        auto_run = not get_setting(st.session_state.db_path, "health_check_passed", "")

        if run_btn or (auto_run and "health_results" not in st.session_state):
            if _HEALTH_CHECK_AVAILABLE:
                with st.spinner("Checking components…"):
                    results = run_all_checks(
                        persist_dir=_chroma_dir(),
                        base_url=get_setting(st.session_state.db_path, "ollama_base_url", "http://localhost:11434") or "http://localhost:11434",
                        model=_ollama_model(),
                        data_dir="data",
                    )
                st.session_state["health_results"] = results
                any_failed = any(r.status == "fail" for r in results)
                set_setting(st.session_state.db_path, "health_check_passed", "" if any_failed else "1")
                set_setting(st.session_state.db_path, "health_check_any_failed", "1" if any_failed else "0")
            else:
                st.warning("health_check module not available.")

        results = st.session_state.get("health_results", [])
        if results:
            _status_colors = {"ok": ("#86efac", "✅"), "warn": ("#fde047", "⚠️"), "fail": ("#fca5a5", "❌")}
            for r in results:
                color, icon = _status_colors.get(r.status, ("#c5cde0", "ℹ️"))
                with st.container(border=True):
                    st.markdown(f"{icon} **{r.name}** — <span style='color:{color}'>{r.message}</span>", unsafe_allow_html=True)
                    if r.fix:
                        st.info(f"💡 Fix: {r.fix}")
            any_failed = any(r.status == "fail" for r in results)
            if any_failed:
                st.error("Fix the issues above before ingesting documents.")
            else:
                st.success("All checks passed. This device is ready.")
```

- [ ] **Step 3: Add banner to render_questions()**

In `render_questions()`, add this block right after the `log_audit(...)` call at line 805:

```python
    if get_setting(st.session_state.db_path, "health_check_any_failed", "0") == "1":
        st.warning(
            "⚠️ Setup incomplete — some components failed the last health check. "
            "Go to **Operations → Setup Health Check** to fix them.",
            icon="⚠️",
        )
```

- [ ] **Step 4: Manual test**

Start the app: `streamlit run app.py`
1. Open Operations → Setup Health Check tab
2. Click "Run checks" — verify all four rows appear with status indicators
3. Navigate to Ask Questions — confirm no banner appears when all checks pass
4. In SQLite, manually set `health_check_any_failed = '1'` in system_settings, reload — confirm banner appears

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add Setup Health Check tab to Operations with first-run auto-check and Ask Questions banner"
```

---

## Task 4: Post-Ingestion Chunk Verification

**Files:**
- Modify: `src/batch_processor.py` — add `verify_chunk_counts()`, add `get_collection` to RAG imports
- Create: `tests/test_chunk_verification.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chunk_verification.py`:

```python
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from src.database import init_database
from src.batch_processor import verify_chunk_counts


def _setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO files (file_path, file_name, extension, file_size, modified_time, file_hash, status, ocr_used, last_processed_at, chroma_synced, chunk_count) "
        "VALUES ('path/a.pdf', 'a.pdf', '.pdf', 100, 0.0, 'abc', 'processed', 0, '2026-01-01', 1, 5)"
    )
    conn.execute(
        "INSERT INTO files (file_path, file_name, extension, file_size, modified_time, file_hash, status, ocr_used, last_processed_at, chroma_synced, chunk_count) "
        "VALUES ('path/b.pdf', 'b.pdf', '.pdf', 200, 0.0, 'def', 'processed', 0, '2026-01-01', 1, 3)"
    )
    conn.commit()
    conn.close()
    return db_path


def _make_collection(counts_by_path: dict):
    col = MagicMock()
    def _get(where, **kwargs):
        fp = where["file_path"]
        n = counts_by_path.get(fp, 0)
        return {"ids": [f"id{i}" for i in range(n)]}
    col.get.side_effect = _get
    return col


def test_verify_all_chunks_present(tmp_path):
    db_path = _setup_db(tmp_path)
    col = _make_collection({"path/a.pdf": 5, "path/b.pdf": 3})
    with patch("src.batch_processor.get_collection", return_value=col):
        results = verify_chunk_counts(db_path, "data/chromadb")
    assert len(results) == 2
    assert all(r["ok"] for r in results)


def test_verify_zero_chunks_flags_file(tmp_path):
    db_path = _setup_db(tmp_path)
    col = _make_collection({"path/a.pdf": 0, "path/b.pdf": 3})
    with patch("src.batch_processor.get_collection", return_value=col):
        results = verify_chunk_counts(db_path, "data/chromadb")
    failed = [r for r in results if not r["ok"]]
    assert len(failed) == 1
    assert failed[0]["file_path"] == "path/a.pdf"
    assert failed[0]["actual_chunks"] == 0


def test_verify_zero_chunks_resets_db_flags(tmp_path):
    db_path = _setup_db(tmp_path)
    col = _make_collection({"path/a.pdf": 0, "path/b.pdf": 3})
    with patch("src.batch_processor.get_collection", return_value=col):
        verify_chunk_counts(db_path, "data/chromadb")
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT chroma_synced, chunk_count FROM files WHERE file_path = 'path/a.pdf'"
    ).fetchone()
    conn.close()
    assert row == (0, 0)


def test_verify_returns_summary_fields(tmp_path):
    db_path = _setup_db(tmp_path)
    col = _make_collection({"path/a.pdf": 5, "path/b.pdf": 3})
    with patch("src.batch_processor.get_collection", return_value=col):
        results = verify_chunk_counts(db_path, "data/chromadb")
    for r in results:
        assert "file_path" in r
        assert "file_name" in r
        assert "expected_chunks" in r
        assert "actual_chunks" in r
        assert "ok" in r


def test_verify_chromadb_unavailable_returns_empty(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch("src.batch_processor._CHROMA_AVAILABLE", False):
        results = verify_chunk_counts(db_path, "data/chromadb")
    assert results == []
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `.venv/Scripts/pytest tests/test_chunk_verification.py -v`
Expected: `ImportError: cannot import name 'verify_chunk_counts'`

- [ ] **Step 3: Add get_collection to RAG imports in batch_processor.py**

Change the RAG import block at line 14–19 from:

```python
try:
    from src.rag.chunker import chunk_text
    from src.rag.vector_store import upsert_document, delete_by_file_path
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False
```

to:

```python
try:
    from src.rag.chunker import chunk_text
    from src.rag.vector_store import upsert_document, delete_by_file_path, get_collection
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False
```

- [ ] **Step 4: Add verify_chunk_counts() and reingest_single_file() to batch_processor.py**

Add both functions after the `sync_missing_to_chroma` function (around line 420):

```python
def verify_chunk_counts(db_path: str, chroma_dir: str) -> list[dict]:
    """Compare each processed file's expected chunk count against ChromaDB.

    Returns a list of dicts: {file_path, file_name, expected_chunks, actual_chunks, ok}.
    Resets chroma_synced=0 and chunk_count=0 in SQLite for any file with actual_chunks=0.
    """
    if not _CHROMA_AVAILABLE:
        return []

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT file_path, file_name, chunk_count FROM files WHERE chroma_synced = 1 AND status = 'processed'"
    )
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return []

    try:
        collection = get_collection(chroma_dir)
    except Exception:
        conn.close()
        return []

    results = []
    for row in rows:
        file_path, file_name, expected = row["file_path"], row["file_name"], row["chunk_count"]
        try:
            res = collection.get(where={"file_path": file_path}, include=[])
            actual = len(res["ids"])
        except Exception:
            actual = -1  # unknown — skip flagging

        ok = actual > 0
        if actual == 0:
            conn.execute(
                "UPDATE files SET chroma_synced = 0, chunk_count = 0 WHERE file_path = ?",
                (file_path,),
            )

        results.append({
            "file_path": file_path,
            "file_name": file_name,
            "expected_chunks": expected,
            "actual_chunks": actual,
            "ok": ok,
        })

    conn.commit()
    conn.close()
    return results


def reingest_single_file(file_path: str, db_path: str, chroma_dir: str) -> int:
    """Re-embed a single file using its stored content_text. Returns new chunk count (0 on failure)."""
    if not _CHROMA_AVAILABLE:
        return 0

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT ar.content_text FROM analysis_results ar "
        "JOIN files f ON f.id = ar.file_id WHERE f.file_path = ?",
        (file_path,),
    )
    row = cur.fetchone()
    conn.close()

    if not row or not row["content_text"]:
        return 0

    result_stub = {"content": row["content_text"]}
    new_count = _sync_to_chroma(result_stub, file_path, chroma_dir)

    if new_count > 0:
        conn2 = get_connection(db_path)
        conn2.execute(
            "UPDATE files SET chroma_synced = 1, chunk_count = ? WHERE file_path = ?",
            (new_count, file_path),
        )
        conn2.commit()
        conn2.close()

    return new_count
```

- [ ] **Step 5: Run tests — confirm they pass**

Run: `.venv/Scripts/pytest tests/test_chunk_verification.py -v`
Expected: all 5 tests PASS

- [ ] **Step 6: Run full test suite — confirm no regressions**

Run: `.venv/Scripts/pytest -v`
Expected: all existing tests still PASS

- [ ] **Step 7: Commit**

```bash
git add src/batch_processor.py tests/test_chunk_verification.py
git commit -m "feat: add verify_chunk_counts to detect silent ChromaDB write failures after ingestion"
```

---

## Task 5: Ingestion Verification UI

**Files:**
- Modify: `app.py` — `render_ingestion()` (line 550), `render_operations()` `tabs[4]` (AI/RAG Settings)

- [ ] **Step 1: Store verification results after upload ingestion**

In `render_ingestion()`, change the upload processing block (around line 569–574) from:

```python
                run_id = process_uploaded_files_to_db(
                    uploads, st.session_state.db_path, mode="Premium", progress_callback=update_up
                )
                st.session_state.last_run_id = run_id
                st.success(f"Completed upload run #{run_id}.")
                log_audit("upload_ingestion", "Ingestion Hub", f"Processed uploaded files into run {run_id}")
```

to:

```python
                run_id = process_uploaded_files_to_db(
                    uploads, st.session_state.db_path, mode="Premium", progress_callback=update_up
                )
                st.session_state.last_run_id = run_id
                if _CHROMA_AVAILABLE and _RAG_IMPORTS_OK:
                    st.session_state["last_verification"] = verify_chunk_counts(
                        st.session_state.db_path, _chroma_dir()
                    )
                st.success(f"Completed upload run #{run_id}.")
                log_audit("upload_ingestion", "Ingestion Hub", f"Processed uploaded files into run {run_id}")
```

- [ ] **Step 2: Store verification results after folder scan**

Apply the same pattern to the folder scan block (around line 588–594):

```python
                run_id = process_folder_to_db(
                    folder_path.strip(), st.session_state.db_path, mode="Premium",
                    recursive=recursive, progress_callback=update_fo,
                )
                st.session_state.last_run_id = run_id
                if _CHROMA_AVAILABLE and _RAG_IMPORTS_OK:
                    st.session_state["last_verification"] = verify_chunk_counts(
                        st.session_state.db_path, _chroma_dir()
                    )
                st.success(f"Completed folder run #{run_id}.")
                log_audit("folder_ingestion", folder_path.strip(), f"Folder processed into run {run_id}")
```

- [ ] **Step 3: Add verify_chunk_counts and reingest_single_file imports to app.py**

At the top of `app.py`, change the batch_processor import block to include both new functions:

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
    verify_chunk_counts,
    reingest_single_file,
    _CHROMA_AVAILABLE,
)
```

- [ ] **Step 4: Render per-file verification results in render_ingestion()**

Replace the existing "Last run summary" block (lines 596–604) with:

```python
    if st.session_state.last_run_id:
        stats = get_run_stats(st.session_state.db_path, st.session_state.last_run_id)
        if stats:
            st.markdown("### Last run summary")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Processed", stats["processed_files"])
            c2.metric("Skipped", stats["skipped_files"])
            c3.metric("Failed", stats["failed_files"])
            c4.metric("Total", stats["total_files"])

        verification = st.session_state.get("last_verification", [])
        if verification:
            ok_count = sum(1 for r in verification if r["ok"])
            bad_count = len(verification) - ok_count
            total_chunks = sum(r["actual_chunks"] for r in verification if r["actual_chunks"] > 0)
            st.markdown("### Index verification")
            vc1, vc2, vc3 = st.columns(3)
            vc1.metric("Indexed OK", ok_count)
            vc2.metric("Missing chunks", bad_count)
            vc3.metric("Total chunks", total_chunks)

            for r in verification:
                if r["ok"]:
                    st.markdown(
                        f"✅ **{r['file_name']}** — {r['actual_chunks']} chunks"
                    )
                else:
                    with st.container(border=True):
                        st.markdown(
                            f"❌ **{r['file_name']}** — 0 chunks — not searchable"
                        )
                        st.caption("ChromaDB did not store any chunks. This file will not appear in Q&A results.")
                        if st.button(f"↺ Re-ingest {r['file_name']}", key=f"reingest_{r['file_path']}"):
                            with st.spinner(f"Re-ingesting {r['file_name']}…"):
                                new_count = reingest_single_file(
                                    r["file_path"], st.session_state.db_path, _chroma_dir()
                                )
                            if new_count > 0:
                                st.success(f"Re-ingested {new_count} chunks.")
                                st.rerun()
                            else:
                                st.error("Re-ingestion produced 0 chunks. The file may have no stored text — re-upload it via the file uploader.")
```

- [ ] **Step 5: Add "Verify & repair index" button to Operations → AI/RAG Settings tab**

In `render_operations()`, inside the `with tabs[4]:` block (AI / RAG Settings), add before the closing of that block:

```python
        st.divider()
        st.markdown("### Index integrity")
        st.write("Scan all indexed files and flag any with missing chunks in ChromaDB.")
        if st.button("Verify & repair index", key="verify_repair_btn"):
            if _CHROMA_AVAILABLE and _RAG_IMPORTS_OK:
                with st.spinner("Verifying chunk counts…"):
                    vresults = verify_chunk_counts(st.session_state.db_path, _chroma_dir())
                broken = [r for r in vresults if not r["ok"]]
                if broken:
                    st.warning(f"{len(broken)} file(s) have missing chunks and have been flagged for re-ingestion.")
                    for r in broken:
                        st.markdown(f"- **{r['file_name']}** — expected {r['expected_chunks']}, found 0 in ChromaDB")
                else:
                    st.success(f"All {len(vresults)} file(s) verified. No missing chunks found.")
            else:
                st.warning("ChromaDB is not available.")
```

- [ ] **Step 6: Manual test**

Start the app: `streamlit run app.py`
1. Upload a file — verify chunk count row appears in green
2. Manually delete a file's chunks from ChromaDB using Operations → AI/RAG Settings → Reset ChromaDB, then re-ingest one file; in SQLite set `chroma_synced=1` for another file manually — verify it shows as ❌
3. Click "Verify & repair index" in Operations — verify broken files are listed

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "feat: show per-file chunk verification results in Ingestion Hub with re-ingest button"
```

---

## Task 6: Structured Error Types in ask_with_rag

**Files:**
- Modify: `src/rag/llm_interface.py`
- Create: `tests/test_llm_interface_errors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_interface_errors.py`:

```python
import pytest
import requests
from unittest.mock import patch, MagicMock
from src.rag.llm_interface import ask_with_rag


def _make_chunks(distances):
    return [
        {"id": str(i), "text": "some content", "metadata": {"file_name": "f.pdf"}, "distance": d}
        for i, d in enumerate(distances)
    ]


def test_no_chunks_returns_error_type():
    llm = MagicMock()
    with patch("src.rag.llm_interface.similarity_search", return_value=[]):
        result = ask_with_rag("what is the risk?", llm)
    assert result["error_type"] == "no_chunks"


def test_low_similarity_returns_error_type():
    llm = MagicMock()
    chunks = _make_chunks([0.92, 0.88, 0.95])  # all above 0.8 threshold
    with patch("src.rag.llm_interface.similarity_search", return_value=chunks):
        result = ask_with_rag("what is the risk?", llm)
    assert result["error_type"] == "low_similarity"


def test_good_similarity_does_not_flag_low_similarity():
    llm = MagicMock()
    chunks = _make_chunks([0.15, 0.92])  # one chunk is good
    with patch("src.rag.llm_interface.similarity_search", return_value=chunks):
        with patch("src.rag.llm_interface._run_chain", return_value="Here is the answer."):
            result = ask_with_rag("what is the risk?", llm)
    assert result["error_type"] is None


def test_ollama_timeout_returns_error_type():
    llm = MagicMock()
    chunks = _make_chunks([0.2, 0.3])
    with patch("src.rag.llm_interface.similarity_search", return_value=chunks):
        with patch("src.rag.llm_interface._run_chain", side_effect=requests.exceptions.Timeout()):
            result = ask_with_rag("what is the risk?", llm)
    assert result["error_type"] == "ollama_timeout"


def test_ollama_connection_error_returns_error_type():
    llm = MagicMock()
    chunks = _make_chunks([0.2])
    with patch("src.rag.llm_interface.similarity_search", return_value=chunks):
        with patch("src.rag.llm_interface._run_chain", side_effect=requests.exceptions.ConnectionError()):
            result = ask_with_rag("what is the risk?", llm)
    assert result["error_type"] == "ollama_timeout"


def test_successful_answer_has_none_error_type():
    llm = MagicMock()
    chunks = _make_chunks([0.1])
    with patch("src.rag.llm_interface.similarity_search", return_value=chunks):
        with patch("src.rag.llm_interface._run_chain", return_value="The risk is high."):
            result = ask_with_rag("what is the risk?", llm)
    assert result["error_type"] is None
    assert result["answer"] == "The risk is high."
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `.venv/Scripts/pytest tests/test_llm_interface_errors.py -v`
Expected: failures — `_run_chain` does not exist, `error_type` key missing

- [ ] **Step 3: Rewrite ask_with_rag in src/rag/llm_interface.py**

Replace the entire `ask_with_rag` function (lines 53–104) with:

```python
_LOW_SIMILARITY_THRESHOLD = 0.8


def _run_chain(chain, prompt_input: dict) -> str:
    """Thin wrapper around chain.invoke — exists so tests can patch it."""
    return chain.invoke(prompt_input)


def ask_with_rag(
    question: str,
    llm: ChatOllama,
    persist_dir: str = "data/chromadb",
    top_k: int = 8,
    chat_history: list[dict] | None = None,
) -> dict:
    """Run a RAG query and return the answer with source references.

    Returns:
        answer       — LLM-generated answer string (empty string on error)
        sources      — list of unique file names cited
        chunks_used  — number of chunks retrieved
        chunks       — raw chunk dicts (for UI display)
        error_type   — None | "no_chunks" | "low_similarity" | "ollama_timeout"
    """
    chunks = similarity_search(question, top_k=top_k, persist_dir=persist_dir)

    if not chunks:
        return {
            "answer": "",
            "sources": [],
            "chunks_used": 0,
            "chunks": [],
            "error_type": "no_chunks",
        }

    if all(c.get("distance", 0) > _LOW_SIMILARITY_THRESHOLD for c in chunks):
        return {
            "answer": "",
            "sources": [],
            "chunks_used": len(chunks),
            "chunks": chunks,
            "error_type": "low_similarity",
        }

    context = _format_docs(chunks)

    history_text = ""
    if chat_history:
        recent = chat_history[-3:]
        history_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in recent
        )

    prompt_input = {
        "context": context,
        "question": question if not history_text else f"{history_text}\nUser: {question}",
    }

    chain = _RAG_PROMPT | llm | StrOutputParser()
    try:
        answer = _run_chain(chain, prompt_input)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, TimeoutError):
        return {
            "answer": "",
            "sources": [],
            "chunks_used": len(chunks),
            "chunks": chunks,
            "error_type": "ollama_timeout",
        }

    sources = list({c["metadata"].get("file_name", "unknown") for c in chunks})

    return {
        "answer": answer,
        "sources": sources,
        "chunks_used": len(chunks),
        "chunks": chunks,
        "error_type": None,
    }
```

- [ ] **Step 4: Run tests — confirm they pass**

Run: `.venv/Scripts/pytest tests/test_llm_interface_errors.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Run full test suite — confirm no regressions**

Run: `.venv/Scripts/pytest -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/rag/llm_interface.py tests/test_llm_interface_errors.py
git commit -m "feat: add error_type to ask_with_rag for no_chunks, low_similarity, and ollama_timeout cases"
```

---

## Task 7: Honest Error Messages in render_questions

**Files:**
- Modify: `app.py` — `_run_question()` helper and `render_questions()`

- [ ] **Step 1: Update _run_question_rag to return the full result dict**

`_run_question_rag` is at line 483 in `app.py`. It currently returns `tuple[str, list[str]] | None`. Change it to return `dict | None` (the full result from `ask_with_rag`):

```python
def _run_question_rag(question: str) -> dict | None:
    llm = _get_llm()
    if llm is None:
        return None

    try:
        result = ask_with_rag(
            question=question,
            llm=llm,
            persist_dir=_chroma_dir(),
            top_k=8,
            chat_history=st.session_state.chat_history,
        )
    except Exception as exc:
        st.warning(f"AI answer failed ({exc}). Falling back to keyword search.")
        return None

    return result
```

- [ ] **Step 2: Update _run_question to unpack the new return type and store error_type**

`_run_question` is at line 503 in `app.py`. Update the RAG result handling block to use the new dict return and store `error_type`:

```python
    if chroma_ok and ollama_ok:
        with st.spinner("Thinking…"):
            rag_result = _run_question_rag(question)
        if rag_result:
            error_type = rag_result.get("error_type")
            if error_type is None:
                answer = rag_result.get("answer", "")
                sources = rag_result.get("sources", [])
            else:
                # Surface the error — don't fall through to TF-IDF
                answer = None
                sources = []
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": "",
                    "sources": [],
                    "error_type": error_type,
                    "time": now,
                })
                return
```

Replace only the `if rag_result:` block inside `_run_question` — leave the rest of the function (TF-IDF fallback) unchanged.

- [ ] **Step 3: Update render_questions() to display error cards**

In `render_questions()`, find where assistant messages are rendered (the `else:` block inside the chat message loop, around line 843). Change it from:

```python
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
                    sources = msg.get("sources") or []
                    if sources:
                        st.markdown(_source_chips_html(sources), unsafe_allow_html=True)
```

to:

```python
            else:
                with st.chat_message("assistant"):
                    error_type = msg.get("error_type")
                    if error_type == "no_chunks":
                        st.error(
                            "❌ No searchable content found for your question. "
                            "The relevant file may have 0 chunks in the vector store. "
                            "Go to **Ingestion Hub** and re-ingest it, or run "
                            "**Operations → AI/RAG Settings → Verify & repair index**."
                        )
                    elif error_type == "low_similarity":
                        st.warning(
                            "⚠️ Found indexed content but none closely matched your question. "
                            "Try rephrasing, or ask about a specific section or file name."
                        )
                    elif error_type == "ollama_timeout":
                        st.error(
                            "❌ Ollama took too long to respond. "
                            "Check it is running: open a terminal and run `ollama serve`. "
                            "If the model is not pulled, run `ollama pull llama3.2:3b`."
                        )
                    elif msg["content"]:
                        st.markdown(msg["content"])
                    sources = msg.get("sources") or []
                    if sources:
                        st.markdown(_source_chips_html(sources), unsafe_allow_html=True)
```

- [ ] **Step 4: Manual test**

Start the app: `streamlit run app.py`
1. Ask a question when ChromaDB is empty — confirm "No searchable content" error appears
2. Ask a very obscure question unrelated to ingested documents — confirm "low similarity" warning appears
3. Stop Ollama (`taskkill /f /im ollama.exe`) and ask a question with documents indexed — confirm "Ollama took too long" error appears

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: replace generic RAG fallback with specific no_chunks, low_similarity, and ollama_timeout error messages"
```

---

## Final Verification

- [ ] **Run full test suite one last time**

Run: `.venv/Scripts/pytest -v`
Expected: all tests PASS with no failures or errors

- [ ] **Smoke test the full flow on a clean state**

1. `streamlit run app.py`
2. Open Operations → Setup Health Check → Run checks — all pass
3. Upload 2–3 documents via Ingestion Hub — all show green with chunk counts
4. Ask a question — receives a proper answer with source chips
5. Ask an off-topic question — receives the low-similarity warning

- [ ] **Final commit**

```bash
git add .
git commit -m "feat: cross-device reliability — pinned deps, health check, chunk verification, honest error messages"
```
