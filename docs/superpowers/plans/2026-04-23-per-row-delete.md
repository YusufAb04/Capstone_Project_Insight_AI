# Per-Row Delete with Auto ChromaDB Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 🗑️ button to every file row in File Explorer that deletes the file plus all its ChromaDB chunks atomically, and remove the now-redundant Reset ChromaDB and Sync buttons from Operations & Recovery.

**Architecture:** Three changes in two files. (1) Add `purge_orphaned_chunks()` to `vector_store.py` to clean up chunks from files deleted before this feature existed. (2) Rewrite the Browse Files tab in `render_file_explorer()` to render a column-based row list with per-row 🗑️ buttons and an inline confirmation panel driven by `st.session_state.pending_delete`. (3) Strip the Sync & Maintenance block out of `render_operations()` and tidy the imports.

**Tech Stack:** Python, Streamlit, ChromaDB (via `src.rag.vector_store`), SQLite (via `src.database`)

---

## File Map

| File | Change |
|------|--------|
| `src/rag/vector_store.py` | Add `purge_orphaned_chunks(db_path, persist_dir)` |
| `app.py` | Update imports, `init_state`, `main`, `render_file_explorer`, `render_operations` |

---

## Task 1: Add `purge_orphaned_chunks` to vector_store.py

**Files:**
- Modify: `src/rag/vector_store.py` (end of file, after `reset_collection`)

- [ ] **Step 1: Append the function**

Open `src/rag/vector_store.py`. After the closing line of `reset_collection`, append:

```python
def purge_orphaned_chunks(db_path: str, persist_dir: str = "data/chromadb") -> int:
    """Delete ChromaDB chunks whose file_path no longer exists in the SQLite files table.

    Called once per session on app startup to clean up chunks left behind by
    files that were deleted before per-row ChromaDB cleanup was introduced.
    Returns the number of chunks removed.
    """
    try:
        collection = get_collection(persist_dir)
        chroma_paths: set[str] = set()
        batch_size = 1000
        offset = 0
        while True:
            results = collection.get(limit=batch_size, offset=offset, include=["metadatas"])
            ids = results.get("ids", [])
            if not ids:
                break
            for meta in results.get("metadatas", []):
                fp = (meta or {}).get("file_path")
                if fp:
                    chroma_paths.add(fp)
            if len(ids) < batch_size:
                break
            offset += batch_size

        if not chroma_paths:
            return 0

        conn = __import__("sqlite3").connect(db_path)
        placeholders = ",".join("?" * len(chroma_paths))
        sqlite_paths = {
            row[0]
            for row in conn.execute(
                f"SELECT file_path FROM files WHERE file_path IN ({placeholders})",
                list(chroma_paths),
            ).fetchall()
        }
        conn.close()

        total = 0
        for fp in chroma_paths - sqlite_paths:
            total += delete_by_file_path(fp, persist_dir)
        return total
    except Exception:
        return 0
```

- [ ] **Step 2: Smoke-test the function**

Run from the project root (using the venv Python):

```
.venv/Scripts/python -c "
import sys; sys.path.insert(0, '.')
import src.rag
from src.rag.vector_store import purge_orphaned_chunks
n = purge_orphaned_chunks('insight_ai_production.db', 'data/chromadb')
print('Orphaned chunks removed:', n)
"
```

Expected: prints `Orphaned chunks removed: <number>` with no exception. The number may be 0 (all clean) or positive (stale chunks cleaned up).

- [ ] **Step 3: Commit**

```bash
git add src/rag/vector_store.py
git commit -m "feat: add purge_orphaned_chunks to vector_store"
```

---

## Task 2: Wire purge into app startup + update imports

**Files:**
- Modify: `app.py` lines 18-47 (imports), 176-182 (`init_state`), 1136-1141 (`main`)

- [ ] **Step 1: Remove `sync_missing_to_chroma` from the batch_processor import block**

In `app.py`, find the `from src.batch_processor import (...)` block (lines 18-28). Remove `sync_missing_to_chroma,` from the list. Result:

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

- [ ] **Step 2: Update the RAG imports block**

Find the `try: from src.rag...` block (lines 41-47). Replace `reset_collection` with `purge_orphaned_chunks` and add `delete_by_file_path`:

```python
try:
    from src.rag.llm_interface import check_ollama_status, get_llm, ask_with_rag
    from src.rag.vector_store import collection_stats, purge_orphaned_chunks, delete_by_file_path
    from src.rag.health import rag_health_report
    _RAG_IMPORTS_OK = True
except ImportError:
    _RAG_IMPORTS_OK = False
```

- [ ] **Step 3: Add session-state keys to `init_state`**

In `init_state()` (line 176), add two new defaults at the end of the function:

```python
def init_state() -> None:
    st.session_state.setdefault("db_path", "insight_ai_production.db")
    st.session_state.setdefault("last_run_id", None)
    st.session_state.setdefault("page", "Home")
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("ollama_ok", None)
    st.session_state.setdefault("rag_llm", None)
    st.session_state.setdefault("pending_delete", None)   # file_path armed for deletion
    st.session_state.setdefault("_chroma_purged", False)  # run purge once per session
```

- [ ] **Step 4: Call purge once in `main()`**

In `main()` (line 1136), after `init_database(st.session_state.db_path)`, insert:

```python
def main() -> None:
    inject_css()
    init_state()
    render_sidebar()
    init_database(st.session_state.db_path)

    # Clean up ChromaDB chunks for files deleted before per-row cleanup existed.
    if _RAG_IMPORTS_OK and _CHROMA_AVAILABLE and not st.session_state._chroma_purged:
        st.session_state._chroma_purged = True
        purge_orphaned_chunks(st.session_state.db_path, persist_dir=_chroma_dir())

    page = st.session_state.page
    ...
```

- [ ] **Step 5: Verify app still boots**

```
.venv/Scripts/python -c "import ast, sys; ast.parse(open('app.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: wire purge_orphaned_chunks into app startup"
```

---

## Task 3: Rewrite `render_file_explorer()` Browse Files tab

**Files:**
- Modify: `app.py` lines 709-791 (the `with tabs[0]:` block)

- [ ] **Step 1: Replace the entire `with tabs[0]:` block**

Find the block starting at `with tabs[0]:` (line 709) and ending just before `with tabs[1]:` (line 793). Replace it entirely with:

```python
    with tabs[0]:
        df = pd.DataFrame(records)
        risk_filter = st.multiselect("Filter risk label", sorted(df["risk_label"].dropna().unique().tolist()))
        ext_filter = st.multiselect("Filter extension", sorted(df["extension"].dropna().unique().tolist()))
        if risk_filter:
            df = df[df["risk_label"].isin(risk_filter)]
        if ext_filter:
            df = df[df["extension"].isin(ext_filter)]
        if df.empty:
            st.info("No files match the current filters.")
            return

        # ── Column header ────────────────────────────────────────────────────
        COL_W = [4, 2, 2, 1, 1]
        h1, h2, h3, h4, h5 = st.columns(COL_W)
        h1.markdown("**File**")
        h2.markdown("**Type**")
        h3.markdown("**Risk**")
        h4.markdown("**Score**")
        h5.markdown("")
        st.divider()

        # ── File rows ────────────────────────────────────────────────────────
        for _, row in df.iterrows():
            fp = row.get("file_path", "")
            fname = row.get("file_name", "")
            c1, c2, c3, c4, c5 = st.columns(COL_W)
            c1.write(fname[:48] + "…" if len(fname) > 48 else fname)
            c2.write(row.get("document_type") or "—")
            c3.write(row.get("risk_label") or "—")
            c4.write(str(row.get("risk_score") or "—"))
            if c5.button("🗑️", key=f"trash_{fp}", help=f"Delete {fname}"):
                st.session_state.pending_delete = fp

        # ── Confirmation panel ───────────────────────────────────────────────
        pending_fp = st.session_state.get("pending_delete")
        if pending_fp:
            match = df[df["file_path"] == pending_fp]
            if match.empty:
                st.session_state.pending_delete = None
            else:
                pending_name = match.iloc[0]["file_name"]
                is_local = pending_fp and not pending_fp.startswith("uploaded://")
                st.divider()
                with st.container(border=True):
                    st.warning(f"🗑️ Remove **{pending_name}** from the index?")
                    del_disk = False
                    if is_local:
                        del_disk = st.checkbox(
                            "Also delete the file from disk (permanent — cannot be undone)",
                            key="del_disk_chk",
                        )
                    btn_col1, btn_col2, _ = st.columns([1, 1, 5])
                    if btn_col1.button("Confirm", type="primary", key="del_confirm_btn"):
                        # Remove from SQLite (CASCADE removes analysis_results)
                        try:
                            conn = get_connection(st.session_state.db_path)
                            conn.cursor().execute("DELETE FROM files WHERE file_path = ?", (pending_fp,))
                            conn.commit()
                            conn.close()
                        except Exception as exc:
                            st.error(f"Database error: {exc}")
                            st.stop()
                        # Remove chunks from ChromaDB
                        if _CHROMA_AVAILABLE and _RAG_IMPORTS_OK:
                            try:
                                delete_by_file_path(pending_fp, persist_dir=_chroma_dir())
                            except Exception as chroma_exc:
                                st.warning(f"Removed from index, but ChromaDB cleanup failed: {chroma_exc}")
                        # Optionally remove from disk
                        if del_disk and is_local:
                            try:
                                Path(pending_fp).unlink(missing_ok=True)
                            except Exception as exc:
                                st.warning(f"Removed from index but could not delete file from disk: {exc}")
                        log_audit(
                            "delete_file",
                            pending_name,
                            f"Deleted from index{' and disk' if del_disk else ''}",
                        )
                        st.session_state.pending_delete = None
                        st.success(f"**{pending_name}** removed.")
                        st.rerun()
                    if btn_col2.button("Cancel", key="del_cancel_btn"):
                        st.session_state.pending_delete = None
                        st.rerun()

        # ── File detail panel ────────────────────────────────────────────────
        st.divider()
        file_choice = st.selectbox("Inspect file", df["file_name"].tolist())
        detail = df[df["file_name"] == file_choice].iloc[0]
        log_audit("view_file", file_choice, "Viewed file explorer details")
        for title, body in [
            ("Summary", detail.get("summary") or "No summary available."),
            ("Management takeaway", detail.get("management_takeaway") or "No management takeaway available."),
            ("Path", detail.get("file_path") or "N/A"),
            ("Risk explanation", detail.get("risk_explanation") or "No risk explanation available."),
        ]:
            render_card(title, body)
        st.markdown("**Keywords**")
        for kw in detail.get("keywords") or []:
            st.markdown(f"<span class='pill'>{kw}</span>", unsafe_allow_html=True)
        st.write(f"**Risk label:** {detail.get('risk_label')}")
        st.write(f"**Risk score:** {detail.get('risk_score')}")
        st.write(f"**OCR used:** {'Yes' if detail.get('ocr_used') else 'No'}")
```

- [ ] **Step 2: Verify syntax**

```
.venv/Scripts/python -c "import ast, sys; ast.parse(open('app.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: per-row trash button in File Explorer with inline ChromaDB cleanup"
```

---

## Task 4: Remove Sync & Reset buttons from `render_operations()`

**Files:**
- Modify: `app.py` lines 1070-1090 (the Sync & Maintenance block inside `tabs[4]`)

- [ ] **Step 1: Delete the Sync & Maintenance section**

Inside `render_operations()`, find the block starting at `st.divider()` / `st.markdown("### Sync & Maintenance")` (line 1070) and ending after the reset button's `log_audit` call (line 1090). Delete those 21 lines entirely. The Ollama setup instructions divider and block immediately follow and should remain untouched.

The `tabs[4]` block after this change ends with:

```python
        if st.button("Save RAG settings"):
            set_setting(st.session_state.db_path, "ollama_model", new_model.strip())
            set_setting(st.session_state.db_path, "chroma_persist_dir", new_chroma.strip())
            st.session_state.rag_llm = None
            st.session_state.ollama_ok = None
            st.success("RAG settings saved.")

        st.divider()
        st.markdown("### Ollama setup instructions")
        st.info(
            "Ollama is not a Python package — it has its own Windows installer.\n\n"
            "1. Download and install Ollama from **ollama.com**\n"
            "2. Open a terminal and run: `ollama pull llama3.2:3b`\n"
            "3. Ollama runs as a background service on `localhost:11434`\n"
            "4. Refresh this page — the status dot in the sidebar will turn green."
        )
```

- [ ] **Step 2: Verify syntax**

```
.venv/Scripts/python -c "import ast, sys; ast.parse(open('app.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: remove reset-chroma and sync buttons from Operations"
```

---

## Task 5: Manual verification

- [ ] **Step 1: Start the app**

```
run.bat
```

or:

```
.venv/Scripts/activate && streamlit run app.py
```

- [ ] **Step 2: Verify File Explorer**

- Open File Explorer tab → Browse Files
- Confirm every file row shows a 🗑️ button on the right
- Click 🗑️ on any file → confirmation panel appears below the list with "Confirm" and "Cancel"
- Click Cancel → panel disappears, file still listed
- Click 🗑️ again → click Confirm → file disappears from list, success message shown
- Open Ask Questions tab → ask something related to the deleted file → answer should NOT reference it

- [ ] **Step 3: Verify Operations & Recovery**

- Open Operations & Recovery → AI / RAG Settings tab
- Confirm "Sync missing documents to ChromaDB" button is gone
- Confirm "Reset ChromaDB collection" button is gone
- Confirm "Save RAG settings" and Ollama setup instructions still present

- [ ] **Step 4: Verify orphan purge on startup**

Check that app restarted cleanly (no error in terminal). The purge runs silently — no UI output is expected.
