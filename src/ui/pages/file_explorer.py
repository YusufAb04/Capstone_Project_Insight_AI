from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.database import get_connection
from src.duplicate_detector import find_duplicates
from src.ui.deps import CHROMA_AVAILABLE, RAG_IMPORTS_OK, delete_by_file_path
from src.ui.helpers import load_records, log_audit, render_card
from src.ui.rag_helpers import _chroma_dir


def render_file_explorer() -> None:
    log_audit("open_page", "File Explorer", "Opened page File Explorer")
    st.title("🗂️ File Explorer")
    records = load_records()
    if not records:
        st.warning("No indexed records yet.")
        return

    tabs = st.tabs(["Browse Files", "Duplicate Files"])

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
            badge = "✨ " if row.get("llm_enriched") == 1 else ""
            display_name = badge + (fname[:46] + "…" if len(fname) > 46 else fname)
            c1.write(display_name)
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
                        if CHROMA_AVAILABLE and RAG_IMPORTS_OK:
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

    with tabs[1]:
        st.markdown("### Duplicate Files")
        st.write("Files with identical content (same SHA-256 hash) stored at multiple paths.")
        dups = find_duplicates(st.session_state.db_path)
        if not dups:
            st.success("No duplicate files detected.")
        else:
            st.warning(f"{len(dups)} duplicate group(s) found.")
            for group in dups:
                with st.expander(f"Hash: {group['file_hash'][:16]}…  ({group['count']} copies)"):
                    for path, name in zip(group["file_paths"], group["file_names"]):
                        col_name, col_btn = st.columns([9, 1])
                        col_name.markdown(f"**{name}** — `{path}`")
                        if col_btn.button("🗑️", key=f"dup_trash_{path}", help=f"Remove duplicate: {name}"):
                            st.session_state.pending_dup_delete = {"file_path": path, "file_name": name}

        # ── Duplicate deletion confirmation panel ────────────────────────────
        pending_dup = st.session_state.get("pending_dup_delete")
        if pending_dup:
            dup_fp = pending_dup["file_path"]
            dup_name = pending_dup["file_name"]
            is_local = dup_fp and not dup_fp.startswith("uploaded://")
            st.divider()
            with st.container(border=True):
                st.warning(f"🗑️ Remove duplicate **{dup_name}** from the index?")
                del_disk_dup = False
                if is_local:
                    del_disk_dup = st.checkbox(
                        "Also delete the file from disk (permanent — cannot be undone)",
                        key="del_dup_disk_chk",
                    )
                btn_col1, btn_col2, _ = st.columns([1, 1, 5])
                if btn_col1.button("Confirm", type="primary", key="del_dup_confirm_btn"):
                    try:
                        conn = get_connection(st.session_state.db_path)
                        conn.cursor().execute("DELETE FROM files WHERE file_path = ?", (dup_fp,))
                        conn.commit()
                        conn.close()
                    except Exception as exc:
                        st.error(f"Database error: {exc}")
                        st.stop()
                    if CHROMA_AVAILABLE and RAG_IMPORTS_OK:
                        try:
                            delete_by_file_path(dup_fp, persist_dir=_chroma_dir())
                        except Exception as chroma_exc:
                            st.warning(f"Removed from index, but ChromaDB cleanup failed: {chroma_exc}")
                    if del_disk_dup and is_local:
                        try:
                            Path(dup_fp).unlink(missing_ok=True)
                        except Exception as exc:
                            st.warning(f"Removed from index but could not delete file from disk: {exc}")
                    log_audit(
                        "delete_duplicate",
                        dup_name,
                        f"Duplicate removed from index{' and disk' if del_disk_dup else ''}",
                    )
                    st.session_state.pending_dup_delete = None
                    st.success(f"Duplicate **{dup_name}** has been removed from the index.")
                    st.rerun()
                if btn_col2.button("Cancel", key="del_dup_cancel_btn"):
                    st.session_state.pending_dup_delete = None
                    st.rerun()
