from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.batch_processor import (
    create_schedule,
    enrich_existing_with_llm,
    list_schedules,
    run_due_schedules,
    update_schedule_status,
    verify_chunk_counts,
)
from src.database import backup_database, get_connection, get_setting, restore_database, set_setting
from src.ui.deps import (
    HEALTH_CHECK_AVAILABLE,
    RAG_IMPORTS_OK,
    get_llm,
    rag_health_report,
    run_all_checks,
)
from src.ui.helpers import log_audit
from src.ui.rag_helpers import _chroma_dir, _ollama_model


def render_operations() -> None:
    log_audit("open_page", "Operations", "Opened page Operations")
    st.title("🛠️ Operations, Scheduling, Backup and Validation")
    tabs = st.tabs(["Scheduled scans", "Backup & recovery", "AI / RAG Settings", "Setup Health Check"])

    with tabs[0]:
        st.markdown("### Scheduled scan jobs")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Schedule name", placeholder="Nightly policy scan")
        path = c2.text_input("Folder path", placeholder=r"C:\CompanyData\Policies")
        freq = c3.selectbox("Frequency", ["hourly", "daily", "weekly"], index=1)
        recursive = st.checkbox("Recursive", value=True)
        notes = st.text_area("Notes", height=80)
        if st.button("Create schedule"):
            if name.strip() and path.strip():
                create_schedule(st.session_state.db_path, name.strip(), path.strip(), freq, recursive=recursive, notes=notes)
                st.success("Schedule created.")
                log_audit("create_schedule", path.strip(), f"Created schedule {name.strip()} ({freq})")
            else:
                st.warning("Schedule name and folder path are required.")
        schedules = list_schedules(st.session_state.db_path)
        if schedules:
            st.markdown("### Existing schedules")
            for sched in schedules:
                with st.expander(f"#{sched['id']} • {sched['schedule_name']} • {sched['frequency']} • {'enabled' if sched['enabled'] else 'disabled'}"):
                    st.write(f"**Path:** {sched['folder_path']}")
                    st.write(f"**Next run:** {sched['next_run_at']}")
                    st.write(f"**Last run:** {sched['last_run_at'] or '-'}")
                    enabled = st.checkbox("Enabled", value=bool(sched["enabled"]), key=f"sched_{sched['id']}")
                    if st.button("Save", key=f"save_sched_{sched['id']}"):
                        update_schedule_status(st.session_state.db_path, sched["id"], enabled)
                        st.success("Schedule updated.")
            if st.button("Run due schedules now"):
                prog = st.progress(0, text="Checking due schedules…")
                def cb(done, total, msg):
                    prog.progress(int((done / max(total, 1)) * 100), text=msg)
                ran = run_due_schedules(st.session_state.db_path, progress_callback=cb)
                st.success(f"Ran {ran} due schedule(s).")
        else:
            st.info("No schedules created yet.")

    with tabs[1]:
        st.markdown("### Database backup")
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        suggested = backup_dir / f"insight_ai_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        if st.button("Create backup now"):
            out = backup_database(st.session_state.db_path, str(suggested))
            st.success(f"Backup created at {out}")
            log_audit("backup_database", out, "Created database backup")
        if suggested.exists():
            st.download_button("Download latest backup", data=suggested.read_bytes(),
                               file_name=suggested.name, mime="application/octet-stream")
        st.markdown("### Restore from uploaded backup")
        restore_file = st.file_uploader("Upload a .db backup file", type=["db"], key="restore_db")
        if restore_file is not None and st.button("Restore database from uploaded backup"):
            temp_restore = backup_dir / f"uploaded_restore_{restore_file.name}"
            temp_restore.write_bytes(restore_file.getvalue())
            restore_database(st.session_state.db_path, str(temp_restore))
            st.success("Database restored.")
            log_audit("restore_database", st.session_state.db_path, f"Restored from {restore_file.name}")

    with tabs[2]:
        st.markdown("### AI / RAG Settings")

        if not RAG_IMPORTS_OK:
            st.error("RAG packages are not installed. Run `setup_all.bat` and choose to install the RAG stack.")
            st.code("pip install chromadb langchain langchain-community langchain-ollama langchain-text-splitters sentence-transformers pysqlite3-binary")
            return

        # Health report
        health = rag_health_report(
            persist_dir=_chroma_dir(),
            ollama_model=_ollama_model(),
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ChromaDB", "OK" if health.get("chromadb_collection_ok") else "Not ready")
        c2.metric("Chunks indexed", health.get("chunk_count", 0))
        c3.metric("Ollama", "Online" if health.get("ollama_reachable") else "Offline")
        c4.metric("Model loaded", "Yes" if health.get("ollama_model_loaded") else "No")

        if health.get("ollama_available_models"):
            st.caption(f"Available Ollama models: {', '.join(health['ollama_available_models'])}")

        st.divider()
        st.info(
            "**Chunking updated:** Documents indexed before this update use smaller 500-character chunks "
            "without section heading prefixes. Re-ingest your files via the Ingestion Hub to enable "
            "heading-aware retrieval and improved Q&A accuracy on large documents."
        )
        st.markdown("### Configuration")
        new_model = st.text_input("Ollama model", value=_ollama_model(), placeholder="llama3.2:3b")
        new_chroma = st.text_input("ChromaDB directory", value=_chroma_dir(), placeholder="data/chromadb")
        if st.button("Save RAG settings"):
            saved_model = new_model.strip()
            set_setting(st.session_state.db_path, "ollama_model", saved_model)
            set_setting(st.session_state.db_path, "chroma_persist_dir", new_chroma.strip())
            st.session_state.rag_llm = None
            st.session_state.ollama_ok = None
            st.success("RAG settings saved.")

            if saved_model and saved_model not in (health.get("ollama_available_models") or []):
                import requests as _req
                import json as _json
                status_box = st.empty()
                status_box.info(f"Downloading model '{saved_model}'… this may take several minutes.")
                try:
                    with _req.post(
                        "http://localhost:11434/api/pull",
                        json={"name": saved_model},
                        stream=True,
                        timeout=900,
                    ) as resp:
                        if resp.status_code != 200:
                            status_box.error(f"Ollama returned {resp.status_code}. Is Ollama running?")
                        else:
                            last_status = ""
                            for raw in resp.iter_lines():
                                if not raw:
                                    continue
                                try:
                                    data = _json.loads(raw)
                                except Exception:
                                    continue
                                if data.get("error"):
                                    status_box.error(f"Pull failed: {data['error']}")
                                    break
                                status_text = data.get("status", "")
                                completed = data.get("completed")
                                total = data.get("total")
                                if completed and total:
                                    pct = int(completed / total * 100)
                                    last_status = f"Downloading '{saved_model}': {pct}%"
                                elif status_text and status_text != last_status:
                                    last_status = status_text
                                if last_status:
                                    status_box.info(last_status)
                            else:
                                status_box.success(f"Model '{saved_model}' downloaded successfully.")
                except _req.exceptions.ConnectionError:
                    status_box.error("Cannot reach Ollama at localhost:11434. Make sure Ollama is running.")
                except _req.exceptions.Timeout:
                    status_box.warning(f"Download timed out. Run `ollama pull {saved_model}` manually in a terminal.")

        st.divider()
        st.markdown("### Index verification")
        if st.button("🔍 Verify & repair index"):
            try:
                with st.spinner("Verifying chunk counts…"):
                    verify_results = verify_chunk_counts(st.session_state.db_path, _chroma_dir())
                if verify_results:
                    broken_ops = [r for r in verify_results if r["status"] == "broken"]
                    table_rows = [
                        {
                            "File": Path(r["file_path"]).name,
                            "DB chunks": r["db_chunk_count"],
                            "ChromaDB chunks": r["chroma_chunk_count"],
                            "Status": r["status"],
                        }
                        for r in verify_results
                    ]
                    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
                    if broken_ops:
                        st.warning(
                            f"{len(broken_ops)} file(s) need re-ingestion. "
                            "Go to Ingestion Hub to re-ingest them."
                        )
                    else:
                        st.success("All indexed files verified — no missing chunks.")
                else:
                    st.info("No indexed files found to verify.")
            except Exception:
                st.warning("Index verification is unavailable. Check that ChromaDB is accessible.")

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

        _enrich_disabled = not health.get("ollama_reachable") or not RAG_IMPORTS_OK
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

        st.divider()
        st.markdown("### Ollama setup instructions")
        st.info(
            "Ollama is not a Python package — it has its own Windows installer.\n\n"
            "1. Download and install Ollama from **ollama.com**\n"
            "2. Open a terminal and run: `ollama pull llama3.2:3b`\n"
            "3. Ollama runs as a background service on `localhost:11434`\n"
            "4. Refresh this page — the status dot in the sidebar will turn green."
        )

    with tabs[3]:
        st.markdown("### Setup Health Check")
        st.write("Verify all components are working correctly before ingesting documents on a new device.")

        run_btn = st.button("▶ Run checks", type="primary")
        auto_run = not get_setting(st.session_state.db_path, "health_check_passed", "")

        if run_btn or (auto_run and "health_results" not in st.session_state):
            if HEALTH_CHECK_AVAILABLE:
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
