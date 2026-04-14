import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.database import (
    init_database,
    get_connection,
    backup_database,
    restore_database,
    get_setting,
    set_setting,
)
from src.batch_processor import (
    process_uploaded_files_to_db,
    process_folder_to_db,
    get_run_stats,
    create_schedule,
    list_schedules,
    update_schedule_status,
    run_due_schedules,
)
from src.exporter import build_export_text_from_records, build_export_json_from_records
from src.file_processor import ocr_status

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None

st.set_page_config(page_title="INSIGHT.AI Production Edition", page_icon="🧠", layout="wide")


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(180deg, #050816 0%, #070b1a 100%); }
        .block-container { padding-top: 1.35rem; padding-bottom: 2rem; max-width: 1300px; }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #171a27 0%, #1d2230 100%);
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        section[data-testid="stSidebar"] * { color: #f5f7fb; }
        h1, h2, h3 { letter-spacing: -0.02em; }
        h1 { font-weight: 800 !important; }
        h2 { font-weight: 700 !important; }
        .card {
            background: rgba(255,255,255,0.025);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 12px;
        }
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.07);
            padding: 14px 16px;
            border-radius: 14px;
        }
        .pill {
            display: inline-block; padding: 4px 10px; border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.1); margin-right: 6px; margin-bottom: 6px;
            background: rgba(255,255,255,0.03);
        }
        .muted { color: #98a2b3; font-size: 0.9rem; }
        .stButton button, .stDownloadButton button { border-radius: 12px !important; font-weight: 600 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("db_path", "insight_ai_production.db")
    st.session_state.setdefault("last_run_id", None)
    st.session_state.setdefault("last_question", "")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_audit(action: str, target: str, details: str) -> None:
    try:
        conn = get_connection(st.session_state.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_logs (username, role, action, target, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("system", "system", action, target, details[:1000], now_str()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def render_card(title: str, body: str) -> None:
    st.markdown(f'<div class="card"><div style="font-weight:700; margin-bottom:8px;">{title}</div><div>{body}</div></div>', unsafe_allow_html=True)


def risk_color(label: str) -> str:
    return {"Low": "#1f9d55", "Medium": "#d69e2e", "High": "#dd6b20", "Critical": "#e53e3e"}.get(label, "#718096")


def _safe_json_loads(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []


def load_records(limit: int = 10000):
    conn = get_connection(st.session_state.db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(analysis_results)")
    analysis_cols = {row[1] for row in cur.fetchall()}

    optional_cols = []
    if "content_text" in analysis_cols:
        optional_cols.append("a.content_text")
    else:
        optional_cols.append("NULL AS content_text")

    if "risk_explanation" in analysis_cols:
        optional_cols.append("a.risk_explanation")
    else:
        optional_cols.append("NULL AS risk_explanation")

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

    cur.execute(select_sql, (limit,))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    records = [dict(zip(cols, row)) for row in rows]
    for r in records:
        r["keywords"] = _safe_json_loads(r.get("keywords_json"))
        r["risk_categories"] = _safe_json_loads(r.get("risk_categories_json"))
        r["flagged_phrases"] = _safe_json_loads(r.get("flagged_phrases_json"))
    return records


def load_errors(limit: int = 200):
    conn = get_connection(st.session_state.db_path)
    cur = conn.cursor()
    cur.execute("SELECT file_path, error_type, error_message, created_at FROM error_logs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def load_run_history(limit: int = 50):
    conn = get_connection(st.session_state.db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, started_at, finished_at, source_type, source_value, total_files, processed_files, skipped_files, failed_files, status FROM processing_runs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def load_audit_logs(limit: int = 200):
    conn = get_connection(st.session_state.db_path)
    cur = conn.cursor()
    cur.execute("SELECT username, role, action, target, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def summarize_dataset(records: list[dict]) -> dict:
    total_files = len(records)
    total_words = sum(r.get("word_count") or 0 for r in records)
    avg_risk = (sum(r.get("risk_score") or 0 for r in records) / total_files) if total_files else 0
    high_critical = sum(1 for r in records if (r.get("risk_label") or "") in {"High", "Critical"})
    return {
        "total_files": total_files,
        "total_words": total_words,
        "avg_risk": avg_risk,
        "high_critical": high_critical,
    }


def render_home():
    log_audit("open_page", "Home", "Opened page Home")
    st.title("🧠 INSIGHT.AI ")
    st.subheader("Production-oriented document intelligence for large local datasets")
    records = load_records()
    s = summarize_dataset(records)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Indexed Files", s["total_files"])
    c2.metric("Total Words", s["total_words"])
    c3.metric("Average Risk", f"{s['avg_risk']:.1f}")
    c4.metric("High/Critical Files", s["high_critical"])
    


def render_ingestion():
    log_audit("open_page", "Ingestion Hub", "Opened page Ingestion Hub")
    st.title("📂 Ingestion Hub")
    left, right = st.columns(2)
    with left:
        st.markdown("### Upload files")
        uploads = st.file_uploader("Supported formats: TXT, CSV, PDF, DOCX", type=["txt", "csv", "pdf", "docx"], accept_multiple_files=True)
        if st.button("Process Uploaded Files", use_container_width=True):
            if not uploads:
                st.warning("Please choose one or more files.")
            else:
                progress = st.progress(0, text="Preparing upload processing...")
                def update(done, total, message):
                    pct = int((done / max(total, 1)) * 100)
                    progress.progress(min(pct, 100), text=message)
                run_id = process_uploaded_files_to_db(uploads, st.session_state.db_path, mode="Premium", progress_callback=update)
                st.session_state.last_run_id = run_id
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
                progress = st.progress(0, text="Preparing folder scan...")
                def update(done, total, message):
                    pct = int((done / max(total, 1)) * 100)
                    progress.progress(min(pct, 100), text=message)
                run_id = process_folder_to_db(folder_path.strip(), st.session_state.db_path, mode="Premium", recursive=recursive, progress_callback=update)
                st.session_state.last_run_id = run_id
                st.success(f"Completed folder run #{run_id}.")
                log_audit("folder_ingestion", folder_path.strip(), f"Folder processed into run {run_id}")

    if st.session_state.last_run_id:
        stats = get_run_stats(st.session_state.db_path, st.session_state.last_run_id)
        if stats:
            st.markdown("### Last run summary")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Processed", stats["processed_files"])
            c2.metric("Skipped", stats["skipped_files"])
            c3.metric("Failed", stats["failed_files"])
            c4.metric("Total", stats["total_files"])


def render_dashboard():
    log_audit("open_page", "Executive Dashboard", "Opened page Executive Dashboard")
    st.title("📈 Executive Dashboard")
    records = load_records()
    if not records:
        st.warning("No indexed records yet. Use Ingestion Hub first.")
        return
    s = summarize_dataset(records)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Indexed Files", s["total_files"])
    c2.metric("Total Words", s["total_words"])
    c3.metric("Average Risk", f"{s['avg_risk']:.1f}")
    c4.metric("High/Critical Files", s["high_critical"])

    df = pd.DataFrame(records)
    st.markdown("### Risk distribution")
    st.bar_chart(df["risk_label"].fillna("Unknown").value_counts())

    st.markdown("### Most recent processed files")
    show_cols = ["file_name", "extension", "document_type", "risk_label", "risk_score", "ocr_used", "last_processed_at"]
    st.dataframe(df[show_cols].head(50), use_container_width=True, hide_index=True)

    st.markdown("### Highest-risk files")
    for _, row in df.sort_values(by=["risk_score", "file_name"], ascending=[False, True]).head(20).iterrows():
        label = row.get("risk_label") or "Unknown"
        color = risk_color(label)
        st.markdown(f"""
        <div class='card'>
            <div style='display:flex;justify-content:space-between;align-items:center;'>
                <div><b>{row.get('file_name')}</b></div>
                <div style='color:{color};font-weight:700;'>{label} ({row.get('risk_score') or 0})</div>
            </div>
            <div class='muted'>{row.get('file_path')}</div>
            <div style='margin-top:8px;'><b>Type:</b> {row.get('document_type') or 'Unknown'}</div>
            <div style='margin-top:6px;'><b>Management takeaway:</b> {row.get('management_takeaway') or 'No takeaway available.'}</div>
        </div>
        """, unsafe_allow_html=True)


def render_file_explorer():
    log_audit("open_page", "File Explorer", "Opened page File Explorer")
    st.title("🗂️ File Explorer")
    records = load_records()
    if not records:
        st.warning("No indexed records yet.")
        return
    df = pd.DataFrame(records)
    risk_filter = st.multiselect("Filter risk label", sorted(df["risk_label"].dropna().unique().tolist()))
    ext_filter = st.multiselect("Filter extension", sorted(df["extension"].dropna().unique().tolist()))
    if risk_filter:
        df = df[df["risk_label"].isin(risk_filter)]
    if ext_filter:
        df = df[df["extension"].isin(ext_filter)]
    table_cols = ["file_name", "extension", "document_type", "risk_label", "risk_score", "ocr_used", "file_path", "last_processed_at"]
    st.dataframe(df[table_cols], use_container_width=True, hide_index=True)
    file_choice = st.selectbox("Inspect file", df["file_name"].tolist())
    row = df[df["file_name"] == file_choice].iloc[0]
    log_audit("view_file", file_choice, "Viewed file explorer details")
    for title, body in [
        ("Summary", row.get("summary") or "No summary available."),
        ("Management takeaway", row.get("management_takeaway") or "No management takeaway available."),
        ("Path", row.get("file_path") or "N/A"),
        ("Risk explanation", row.get("risk_explanation") or "No risk explanation available."),
    ]:
        render_card(title, body)
    st.markdown("**Keywords**")
    for kw in row.get("keywords") or []:
        st.markdown(f"<span class='pill'>{kw}</span>", unsafe_allow_html=True)
    st.write(f"**Risk label:** {row.get('risk_label')}")
    st.write(f"**Risk score:** {row.get('risk_score')}")
    st.write(f"**OCR used:** {'Yes' if row.get('ocr_used') else 'No'}")


def _score_question_against_record(question: str, record: dict) -> tuple[float, str]:
    text = " ".join([
        record.get("summary") or "",
        record.get("management_takeaway") or "",
        " ".join(record.get("keywords") or []),
        " ".join(record.get("flagged_phrases") or []),
        record.get("content_text") or "",
    ])
    if not text.strip():
        return 0.0, ""
    if TfidfVectorizer is not None and cosine_similarity is not None:
        try:
            vec = TfidfVectorizer(stop_words="english")
            matrix = vec.fit_transform([question, text])
            score = float(cosine_similarity(matrix[0:1], matrix[1:2]).flatten()[0])
        except Exception:
            score = 0.0
    else:
        q_terms = set(question.lower().split())
        t_terms = text.lower().split()
        score = sum(t_terms.count(term) for term in q_terms)
    excerpt = next((sent for sent in (text.split(". ")) if any(tok in sent.lower() for tok in question.lower().split()[:4])), text[:300])
    return score, excerpt.strip()


def render_questions():
    log_audit("open_page", "Ask Questions", "Opened page Ask Questions")
    st.title("❓ Ask Questions")
    st.write("Ask management-style questions across the indexed dataset. Answers are grounded in stored summaries, takeaways, keywords, flagged phrases, and extracted content.")
    suggestions = [
        "What are the main risks management should focus on right now?",
        "Which files are the highest risk and why?",
        "Are there repeated compliance or security issues across the dataset?",
        "What opportunities for improvement appear across these documents?",
    ]
    c1, c2 = st.columns(2)
    for i, s in enumerate(suggestions):
        with (c1 if i % 2 == 0 else c2):
            if st.button(s, key=f"q_{i}"):
                st.session_state.last_question = s
    question = st.text_area("Your question", value=st.session_state.last_question, height=110)
    if st.button("Generate Answer", use_container_width=True):
        st.session_state.last_question = question
        log_audit("ask_question", "Ask Questions", question)
    if not st.session_state.last_question:
        return
    records = load_records()
    scored = []
    for rec in records:
        score, excerpt = _score_question_against_record(st.session_state.last_question, rec)
        if score > 0:
            scored.append((score, excerpt, rec))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:4]
    if not top:
        st.warning("No strong evidence matched the current question.")
        return
    top_labels = Counter((rec.get("risk_label") or "Unknown") for _, _, rec in top)
    top_types = Counter((rec.get("document_type") or "Unknown") for _, _, rec in top)
    risk_categories = Counter(cat for _, _, rec in top for cat in (rec.get("risk_categories") or []))
    flagged = Counter(flag for _, _, rec in top for flag in (rec.get("flagged_phrases") or []))
    conf = "High" if top[0][0] > 0.15 or len(top) >= 3 else "Moderate"
    answer = (
        f"Based on indexed evidence, the strongest signals are concentrated in {', '.join(rec.get('file_name') for _, _, rec in top[:3])}. "
        f"Confidence: {conf}. Common risk levels across the most relevant files are {', '.join(f'{k} ({v})' for k, v in top_labels.items())}. "
        f"Dominant risk categories: {', '.join(k for k, _ in risk_categories.most_common(4))}. "
        f"Most repeated evidence signals: {', '.join(k for k, _ in flagged.most_common(6))}. Relevant document types: {', '.join(f'{k} ({v})' for k, v in top_types.items())}."
    )
    render_card("Answer", answer)
    st.markdown("### Evidence used")
    for score, excerpt, rec in top:
        render_card(
            rec.get("file_name"),
            f"<b>Relevance score:</b> {score:.2f}<br><b>Type:</b> {rec.get('document_type')}<br><b>Risk:</b> {rec.get('risk_label')} ({rec.get('risk_score')})<br><b>Matched excerpt:</b> {excerpt}<br><b>Management takeaway:</b> {rec.get('management_takeaway')}",
        )


def render_operations():
    log_audit("open_page", "Operations", "Opened page Operations")
    st.title("🛠️ Operations, Scheduling, Backup and Validation")
    tabs = st.tabs(["Scheduled scans", "Backup & recovery", "OCR diagnostics", "Validation metrics"])

    with tabs[0]:
        st.markdown("### Scheduled scan jobs")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Schedule name", placeholder="Nightly policy scan")
        path = c2.text_input("Folder path", placeholder=r"C:\CompanyData\Policies")
        freq = c3.selectbox("Frequency", ["hourly", "daily", "weekly"], index=1)
        recursive = st.checkbox("Recursive", value=True)
        notes = st.text_area("Notes", height=80, placeholder="Runs on a secure internal share")
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
                    st.write(f"**Notes:** {sched['notes'] or '-'}")
                    enabled = st.checkbox("Enabled", value=bool(sched['enabled']), key=f"sched_{sched['id']}")
                    if st.button("Save schedule status", key=f"save_sched_{sched['id']}"):
                        update_schedule_status(st.session_state.db_path, sched['id'], enabled)
                        st.success("Schedule updated.")
            if st.button("Run due schedules now"):
                progress = st.progress(0, text="Checking due schedules...")
                def cb(done, total, msg):
                    pct = int((done / max(total, 1)) * 100)
                    progress.progress(min(pct, 100), text=msg)
                ran = run_due_schedules(st.session_state.db_path, progress_callback=cb)
                progress.progress(100, text="Schedule execution complete.")
                st.success(f"Ran {ran} due schedule(s).")
                log_audit("run_due_schedules", "Operations", f"Ran {ran} due schedules")
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
            st.download_button("Download latest backup", data=suggested.read_bytes(), file_name=suggested.name, mime="application/octet-stream")
        st.markdown("### Restore from uploaded backup")
        restore_file = st.file_uploader("Upload a .db backup file", type=["db"], key="restore_db")
        if restore_file is not None and st.button("Restore database from uploaded backup"):
            temp_restore = backup_dir / f"uploaded_restore_{restore_file.name}"
            temp_restore.write_bytes(restore_file.getvalue())
            restore_database(st.session_state.db_path, str(temp_restore))
            st.success("Database restored from uploaded backup.")
            log_audit("restore_database", st.session_state.db_path, f"Restored from {restore_file.name}")

    with tabs[2]:
        status = ocr_status()
        st.markdown("### OCR runtime diagnostics")
        c1, c2, c3 = st.columns(3)
        c1.metric("pytesseract import", "Available" if status["pytesseract"] else "Missing")
        c2.metric("pdf2image import", "Available" if status["pdf2image"] else "Missing")
        c3.metric("OCR ready", "Yes" if status["available"] else "No")
        st.info("For full OCR in production you still need native Tesseract OCR and Poppler installed on the host machine.")
        enabled = st.checkbox("Enable OCR fallback", value=get_setting(st.session_state.db_path, "ocr_enabled", "1") == "1")
        page_limit = st.number_input("OCR page limit per PDF", min_value=1, max_value=200, value=int(get_setting(st.session_state.db_path, "ocr_page_limit", "30")))
        dpi = st.number_input("OCR DPI", min_value=100, max_value=400, value=int(get_setting(st.session_state.db_path, "ocr_dpi", "220")))
        min_words = st.number_input("Minimum extracted words before OCR fallback", min_value=1, max_value=500, value=int(get_setting(st.session_state.db_path, "ocr_min_words_threshold", "30")))
        if st.button("Save OCR settings"):
            set_setting(st.session_state.db_path, "ocr_enabled", "1" if enabled else "0")
            set_setting(st.session_state.db_path, "ocr_page_limit", str(page_limit))
            set_setting(st.session_state.db_path, "ocr_dpi", str(dpi))
            set_setting(st.session_state.db_path, "ocr_min_words_threshold", str(min_words))
            st.success("OCR settings saved.")
            log_audit("save_ocr_settings", "Operations", f"ocr_enabled={enabled}, page_limit={page_limit}, dpi={dpi}, min_words={min_words}")

    with tabs[3]:
        st.markdown("### Validation against labeled internal dataset")
        st.write("Upload a CSV with columns: `file_name`, optional `expected_risk_label`, optional `expected_document_type`.")
        val_file = st.file_uploader("Upload validation CSV", type=["csv"], key="val_csv")
        if val_file is not None:
            val_df = pd.read_csv(val_file)
            st.dataframe(val_df.head(20), use_container_width=True, hide_index=True)
            if st.button("Run validation"):
                records = {r["file_name"]: r for r in load_records()}
                total = 0
                risk_ok = 0
                doc_ok = 0
                matched = 0
                details = []
                for _, row in val_df.iterrows():
                    fname = str(row.get("file_name", "")).strip()
                    if not fname:
                        continue
                    total += 1
                    rec = records.get(fname)
                    if not rec:
                        details.append([fname, row.get("expected_risk_label"), None, row.get("expected_document_type"), None, 0])
                        continue
                    matched += 1
                    risk_match = str(row.get("expected_risk_label", "")).strip().lower() == str(rec.get("risk_label", "")).strip().lower() if pd.notna(row.get("expected_risk_label")) and str(row.get("expected_risk_label", "")).strip() else None
                    doc_match = str(row.get("expected_document_type", "")).strip().lower() == str(rec.get("document_type", "")).strip().lower() if pd.notna(row.get("expected_document_type")) and str(row.get("expected_document_type", "")).strip() else None
                    if risk_match is True:
                        risk_ok += 1
                    if doc_match is True:
                        doc_ok += 1
                    details.append([fname, row.get("expected_risk_label"), rec.get("risk_label"), row.get("expected_document_type"), rec.get("document_type"), 1 if ((risk_match is True) or (doc_match is True)) else 0])
                risk_acc = (risk_ok / max(sum(1 for x in val_df.get("expected_risk_label", []) if pd.notna(x) and str(x).strip()), 1)) * 100 if "expected_risk_label" in val_df.columns else 0
                doc_acc = (doc_ok / max(sum(1 for x in val_df.get("expected_document_type", []) if pd.notna(x) and str(x).strip()), 1)) * 100 if "expected_document_type" in val_df.columns else 0
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Rows in validation file", total)
                c2.metric("Matched indexed files", matched)
                c3.metric("Risk label accuracy", f"{risk_acc:.1f}%")
                c4.metric("Document type accuracy", f"{doc_acc:.1f}%")
                st.dataframe(pd.DataFrame(details, columns=["file_name", "expected_risk_label", "predicted_risk_label", "expected_document_type", "predicted_document_type", "matched"]), use_container_width=True, hide_index=True)
                conn = get_connection(st.session_state.db_path)
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO validation_runs (started_at, completed_at, dataset_name, total_rows, matched_rows, risk_accuracy, doc_type_accuracy, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (now_str(), now_str(), getattr(val_file, 'name', 'uploaded_validation.csv'), total, matched, risk_acc, doc_acc, 'Validation executed from app'),
                )
                run_id = cur.lastrowid
                for row in details:
                    cur.execute(
                        "INSERT INTO validation_details (validation_run_id, file_name, expected_risk_label, predicted_risk_label, expected_document_type, predicted_document_type, matched) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (run_id, row[0], row[1], row[2], row[3], row[4], row[5]),
                    )
                conn.commit()
                conn.close()
                log_audit("run_validation", getattr(val_file, 'name', 'validation.csv'), f"Validation run {run_id} with risk_acc={risk_acc:.1f}, doc_acc={doc_acc:.1f}")


def render_reports():
    log_audit("open_page", "Reports and Logs", "Opened page Reports and Logs")
    st.title("📝 Reports and Logs")
    records = load_records()
    txt = build_export_text_from_records(records)
    js = build_export_json_from_records(records)
    c1, c2 = st.columns(2)
    with c1:
        if st.download_button("Download TXT Executive Report", txt, file_name="insight_ai_production_report.txt", mime="text/plain", use_container_width=True):
            log_audit("download_report", "TXT", "Downloaded TXT executive report")
    with c2:
        if st.download_button("Download JSON Executive Report", js, file_name="insight_ai_production_report.json", mime="application/json", use_container_width=True):
            log_audit("download_report", "JSON", "Downloaded JSON executive report")
    st.markdown("### Processing run history")
    run_history = load_run_history()
    st.dataframe(pd.DataFrame(run_history), use_container_width=True, hide_index=True)
    st.markdown("### Error log")
    errors = load_errors()
    if errors:
        st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)
    else:
        st.success("No errors logged.")
    st.markdown("### Audit log")
    st.dataframe(pd.DataFrame(load_audit_logs()), use_container_width=True, hide_index=True)


def main():
    inject_css()
    init_state()
    st.sidebar.title("INSIGHT.AI Production Edition")
    st.sidebar.caption("Production-oriented internal document intelligence")
    st.sidebar.text_input("SQLite database path", key="db_path")
    if st.sidebar.button("Initialize / Upgrade Database", use_container_width=True):
        init_database(st.session_state.db_path)
        st.sidebar.success("Database is ready.")
        log_audit("initialize_database", st.session_state.db_path, "Initialized or upgraded database")

    st.sidebar.info("Analysis mode: Premium only")

    page = st.sidebar.radio(
        "Navigation",
        [
            "Home",
            "Ingestion Hub",
            "Executive Dashboard",
            "File Explorer",
            "Ask Questions",
            "Operations & Recovery",
            "Reports and Logs",
        ],
    )

    init_database(st.session_state.db_path)

    if page == "Home":
        render_home()
    elif page == "Ingestion Hub":
        render_ingestion()
    elif page == "Executive Dashboard":
        render_dashboard()
    elif page == "File Explorer":
        render_file_explorer()
    elif page == "Ask Questions":
        render_questions()
    elif page == "Operations & Recovery":
        render_operations()
    elif page == "Reports and Logs":
        render_reports()


if __name__ == "__main__":
    main()
