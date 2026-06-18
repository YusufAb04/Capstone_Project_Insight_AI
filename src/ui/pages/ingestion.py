from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.batch_processor import (
    _CHROMA_AVAILABLE,
    get_run_stats,
    process_folder_to_db,
    process_uploaded_files_to_db,
    reingest_single_file,
    verify_chunk_counts,
)
from src.database import get_exclusion_keywords, set_exclusion_keywords
from src.ui.deps import RAG_IMPORTS_OK
from src.ui.helpers import log_audit
from src.ui.rag_helpers import _chroma_dir


def render_ingestion() -> None:
    log_audit("open_page", "Ingestion Hub", "Opened page Ingestion Hub")
    st.title("📂 Ingestion Hub")

    tab_ingest, tab_exclusion = st.tabs(["Ingest", "Exclusion Keywords"])

    with tab_ingest:
        left, right = st.columns(2)
        with left:
            st.markdown("### Upload files")
            uploads = st.file_uploader(
                "Supported formats: TXT, CSV, PDF, DOCX, XLSX",
                type=["txt", "csv", "pdf", "docx", "xlsx"],
                accept_multiple_files=True,
            )
            if st.button("Process Uploaded Files", use_container_width=True):
                if not uploads:
                    st.warning("Please choose one or more files.")
                else:
                    progress = st.progress(0, text="Preparing upload processing…")
                    def update_up(done, total, message):
                        pct = int((done / max(total, 1)) * 100)
                        progress.progress(min(pct, 100), text=message)
                    run_id, excluded = process_uploaded_files_to_db(
                        uploads, st.session_state.db_path, mode="Premium", progress_callback=update_up
                    )
                    st.session_state.last_run_id = run_id
                    st.session_state.last_excluded = excluded
                    _stats = get_run_stats(st.session_state.db_path, run_id)
                    if _stats and _stats["processed_files"] > 0:
                        st.success(f"Completed upload run #{run_id}.")
                    log_audit("upload_ingestion", "Ingestion Hub", f"Processed uploaded files into run {run_id}")

        with right:
            st.markdown("### Scan local folder")
            folder_path = st.text_input("Folder path", placeholder=r"C:\CompanyData\Policies")
            recursive = st.checkbox("Scan subfolders recursively", value=True)
            if st.button("Scan Folder and Process Changed Files", use_container_width=True):
                if not folder_path.strip():
                    st.warning("Please enter a valid folder path.")
                else:
                    progress = st.progress(0, text="Preparing folder scan…")
                    def update_fo(done, total, message):
                        pct = int((done / max(total, 1)) * 100)
                        progress.progress(min(pct, 100), text=message)
                    run_id, excluded = process_folder_to_db(
                        folder_path.strip(), st.session_state.db_path, mode="Premium",
                        recursive=recursive, progress_callback=update_fo,
                    )
                    st.session_state.last_run_id = run_id
                    st.session_state.last_excluded = excluded
                    _stats = get_run_stats(st.session_state.db_path, run_id)
                    if _stats and _stats["processed_files"] > 0:
                        st.success(f"Completed folder run #{run_id}.")
                    log_audit("folder_ingestion", folder_path.strip(), f"Folder processed into run {run_id}")

        # Exclusion warnings from last run
        if st.session_state.last_excluded:
            st.markdown("### Excluded files")
            for fname, kw in st.session_state.last_excluded:
                st.markdown(
                    f'<div style="background:#7f1d1d;border:1px solid #ef4444;border-radius:6px;'
                    f'padding:12px 16px;margin:6px 0;color:#fecaca;font-size:1.3rem;">'
                    f'<b>{fname}</b> contains keyword <b>\'{kw}\'</b> and was excluded from ingestion.'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if st.session_state.last_run_id:
            stats = get_run_stats(st.session_state.db_path, st.session_state.last_run_id)
            if stats:
                st.markdown("### Last run summary")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Processed", stats["processed_files"])
                c2.metric("Skipped", stats["skipped_files"])
                c3.metric("Failed", stats["failed_files"])
                c4.metric("Excluded", len(st.session_state.last_excluded))
                c5.metric("Total", stats["total_files"])

            # Chunk verification after ingestion
            if _CHROMA_AVAILABLE and RAG_IMPORTS_OK:
                chroma_dir = _chroma_dir()
                try:
                    verify_results = verify_chunk_counts(st.session_state.db_path, chroma_dir)
                    if verify_results:
                        st.markdown("### Index verification")
                        ok_files = [r for r in verify_results if r["status"] == "ok"]
                        broken_files = [r for r in verify_results if r["status"] == "broken"]
                        total_chunks = sum(r["chroma_chunk_count"] for r in verify_results)
                        st.caption(
                            f"{len(ok_files)} indexed OK / {len(broken_files)} with missing chunks / total {total_chunks} chunks"
                        )
                        for r in verify_results:
                            filename = Path(r["file_path"]).name
                            if r["status"] == "ok":
                                st.success(f"✅ {filename} — {r['chroma_chunk_count']} chunks")
                            else:
                                st.error(f"❌ {filename} — 0 chunks, not searchable")
                                if st.button(f"↺ Re-ingest {filename}", key=f"reingest_{r['file_path']}"):
                                    with st.spinner(f"Re-ingesting {filename}…"):
                                        result = reingest_single_file(
                                            st.session_state.db_path, r["file_path"], chroma_dir
                                        )
                                    if result["success"]:
                                        st.success(f"Re-ingested: {result['chunk_count']} chunks")
                                    else:
                                        st.error(f"Re-ingest failed: {result['error']}")
                except Exception:
                    st.warning("Index verification is unavailable. Check that ChromaDB is accessible.")

    with tab_exclusion:
        st.markdown("### Exclusion Keywords")
        st.caption(
            "Files whose names contain any of these keywords (case-insensitive) will be blocked at ingestion — "
            "they won't appear in the database, file explorer, or search results."
        )

        keywords = get_exclusion_keywords(st.session_state.db_path)

        if keywords:
            st.markdown("**Active keywords:**")
            cols = st.columns(min(len(keywords), 4))
            for i, kw in enumerate(keywords):
                with cols[i % min(len(keywords), 4)]:
                    if st.button(f"✕  {kw}", key=f"remove_kw_{i}", help=f"Remove '{kw}'"):
                        keywords.pop(i)
                        set_exclusion_keywords(st.session_state.db_path, keywords)
                        st.rerun()
        else:
            st.info("No exclusion keywords set. All files will be ingested.")

        st.markdown("---")
        with st.form("add_exclusion_kw_form", clear_on_submit=True):
            new_kw = st.text_input("New keyword", placeholder="e.g. CONFIDENTIAL")
            submitted = st.form_submit_button("Add Keyword", use_container_width=True)
            if submitted:
                clean = new_kw.strip()
                if not clean:
                    st.warning("Please enter a keyword.")
                elif clean.lower() in [k.lower() for k in keywords]:
                    st.warning(f"'{clean}' is already in the list.")
                else:
                    keywords.append(clean)
                    set_exclusion_keywords(st.session_state.db_path, keywords)
                    st.success(f"Added '{clean}'.")
                    st.rerun()
