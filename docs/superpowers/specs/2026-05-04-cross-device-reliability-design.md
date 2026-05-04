# Cross-Device Reliability — Design Spec

**Date:** 2026-05-04
**Branch:** cpp-installation
**Status:** Approved for implementation

---

## Problem

INSIGHT_AI gives inconsistent RAG answers across devices after fresh ingestion of the same documents. All components (Ollama, ChromaDB) appear to be running, but some devices return "indexed documents don't have enough information" while others answer correctly for the identical question.

### Root Causes (in order of probability)

1. **Dependency version drift** — `pip install` without pinned versions resolves different package versions on different machines. A different `sentence-transformers` version produces different embeddings → different similarity scores → different retrieval results.
2. **Silent ChromaDB write failures** — Ingestion sets `chroma_synced = 1` in SQLite even when ChromaDB silently fails mid-batch (pysqlite3 compat issue, disk error). Files appear indexed but have zero chunks and will never appear in Q&A.
3. **No first-run validation** — Nothing verifies the embedding model is fully downloaded and working before ingestion. A partial download produces nonsense embeddings that the app cannot detect.
4. **Vague error messages** — "indexed documents don't have enough information" gives no actionable information. The user cannot tell if the problem is zero chunks, low similarity, or an Ollama timeout.

---

## Solution: Four-Part Reliability Hardening

### Part 1 — Pinned `requirements.txt`

**Goal:** Guarantee identical environments across all devices.

- Create `requirements.txt` in the project root with exact pinned versions for every dependency confirmed to work together.
- CLAUDE.md install instructions updated to reference `pip install -r requirements.txt`.
- Covers: `streamlit`, `pandas`, `PyPDF2`, `python-docx`, `scikit-learn`, `chromadb==0.5.23`, `langchain==0.3.25`, `langchain-community==0.3.25`, `langchain-ollama==0.2.5`, `langchain-text-splitters==0.3.8`, `sentence-transformers`, `pysqlite3-binary`.

**Files changed:** `requirements.txt` (new), `CLAUDE.md` (updated install section)

---

### Part 2 — First-Run Setup Health Check

**Goal:** Surface broken components before the user ingests anything, with specific fix instructions.

#### UI
- New tab **"Setup Health Check"** added to the Operations page (after the existing "AI / RAG Settings" tab).
- Four component rows, each showing ✅ / ⚠️ / ❌ with an inline fix instruction:
  - **Embedding model (all-MiniLM-L6-v2)** — downloads model if missing, runs a test encode, verifies output is 384 dimensions.
  - **ChromaDB vector store** — creates a temp test collection, writes and reads one record, verifies the pysqlite3 patch is active.
  - **Ollama LLM** — pings the Ollama API, verifies the configured model is pulled and responding.
  - **SQLite / disk** — verifies the data directory is writable and not inside a cloud-sync folder. Detection: check if the resolved `data/` path contains any of `"OneDrive"`, `"Google Drive"`, `"Dropbox"`, `"iCloudDrive"` as substrings (case-insensitive).
- "Run checks again" button re-runs all checks.
- Timestamp shown for last check.

#### Behavior
- Runs automatically on first launch. A flag `health_check_passed` is stored in `system_settings` after all checks pass. Not re-run automatically once passed.
- If any check failed on last run, a banner appears on the Ask Questions page: *"Setup incomplete — some components failed. Fix in Operations → Setup Health Check."*
- Ingestion is not blocked by failures — a warning is shown inline instead.

#### Implementation
- New module `src/health_check.py` with one function per component returning `{status, message, fix}`.
- Health check tab rendered in `render_operations()` in `app.py`.

**Files changed:** `src/health_check.py` (new), `app.py`

---

### Part 3 — Post-Ingestion Chunk Verification

**Goal:** Catch silent ChromaDB write failures immediately after ingestion, before the user tries Q&A.

#### Logic
After each ingestion run (upload or folder scan), for every processed file:
1. Query ChromaDB for actual chunk count using `file_path` metadata filter.
2. Compare to `chunk_count` stored in the SQLite `files` table.
3. If ChromaDB count = 0 and `chroma_synced = 1` → flag as broken, reset `chroma_synced = 0`, set `chunk_count = 0`.

#### UI — Ingestion Results Panel
The existing post-run summary is extended with per-file status rows:
- ✅ File name + actual chunk count (e.g., "84 chunks")
- ❌ File name + "0 chunks — not searchable" + **"↺ Re-ingest this file"** button

Summary bar at top shows: "N indexed OK / M missing chunks / total chunks."

#### Repair
- **"↺ Re-ingest this file"** — re-runs chunking + embedding for that single file only.
- **"Verify & repair index"** button added to Operations → AI / RAG Settings — runs verification across all files in the database and lists any with broken chunks.

#### Implementation
- Verification logic added to `src/batch_processor.py` as `verify_chunk_counts(db_path, chroma_dir)`.
- Called automatically at end of `process_uploaded_files_to_db` and `process_folder_to_db`.
- Results returned to `app.py` for display.

**Files changed:** `src/batch_processor.py`, `app.py`

---

### Part 4 — Honest Error Messages in Q&A

**Goal:** Replace the single generic fallback message with specific, actionable diagnostics.

#### Three distinct error states

| Condition | Message shown |
|-----------|--------------|
| Zero chunks found for the queried files | "No searchable content found. [filename] has 0 chunks — go to Ingestion Hub and re-ingest it." |
| Chunks found but all retrieved chunks have cosine distance > 0.8 (ChromaDB L2-normalised scale) | "Found content but nothing closely matched your question. Try rephrasing or ask about a specific section." |
| Ollama timeout / connection error | "Ollama took too long to respond. Check it's running: open a terminal and run `ollama serve`." |

#### Implementation
- `ask_with_rag()` in `src/rag/llm_interface.py` returns a structured result with `{answer, sources, error_type}` where `error_type` is one of `"no_chunks"`, `"low_similarity"`, `"ollama_timeout"`, `None`.
- `render_questions()` in `app.py` renders the appropriate error card based on `error_type`.

**Files changed:** `src/rag/llm_interface.py`, `app.py`

---

## Error Handling

- Health checks must never crash the app — all checks are wrapped in try/except and return a failed status on exception.
- Chunk verification failures (e.g., ChromaDB unreachable during verify) are logged to `error_logs` and shown as a warning, not a hard error.
- Re-ingest button is idempotent — safe to press multiple times.

---

## Testing

- **Unit:** `src/health_check.py` — mock each component to return pass/warn/fail, assert correct status and fix text.
- **Unit:** `verify_chunk_counts()` — mock ChromaDB returning 0 chunks, assert `chroma_synced` is reset to 0.
- **Integration:** Ingest a file, manually delete its chunks from ChromaDB, run verification, assert file is flagged.
- **Manual:** Install fresh on a second device using `requirements.txt`, ingest documents, confirm chunk counts match.

---

## Out of Scope

- Syncing documents or databases between devices (project is intentionally local-first).
- Supporting cloud LLM providers as fallback.
- Auto-updating pinned dependency versions.
