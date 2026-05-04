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
    enrich_existing_with_llm,
    _CHROMA_AVAILABLE,
)
from src.exporter import build_export_text_from_records, build_export_json_from_records
from src.file_processor import ocr_status
from src.duplicate_detector import find_duplicates

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None

# RAG imports (optional — graceful fallback if not installed)
try:
    from src.rag.llm_interface import check_ollama_status, get_llm, ask_with_rag
    from src.rag.vector_store import collection_stats, purge_orphaned_chunks, delete_by_file_path
    from src.rag.health import rag_health_report
    _RAG_IMPORTS_OK = True
except ImportError:
    _RAG_IMPORTS_OK = False

try:
    from src.health_check import run_all_checks, CheckResult
    _HEALTH_CHECK_AVAILABLE = True
except ImportError:
    _HEALTH_CHECK_AVAILABLE = False

st.set_page_config(
    page_title="INSIGHT.AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #1a1b25; }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 6rem;
            max-width: 820px;
            margin-left: auto;
            margin-right: auto;
        }
        section[data-testid="stSidebar"] {
            background: #161720;
            border-right: 1px solid rgba(255,255,255,0.05);
        }
        section[data-testid="stSidebar"] * { color: #c5cde0; }
        section[data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
            background: transparent !important;
            border: 1px solid transparent !important;
            color: #b0b8ce !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 9px 14px !important;
            border-radius: 8px !important;
            font-size: 0.875rem !important;
            font-weight: 400 !important;
            width: 100% !important;
            box-shadow: none !important;
            transition: background 0.12s, color 0.12s !important;
        }
        section[data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover {
            background: rgba(255,255,255,0.07) !important;
            color: #fff !important;
        }
        section[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
            background: rgba(255,255,255,0.08) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            color: #ffffff !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 9px 14px !important;
            border-radius: 8px !important;
            font-size: 0.875rem !important;
            font-weight: 500 !important;
            width: 100% !important;
            box-shadow: none !important;
        }
        h1, h2, h3 { letter-spacing: -0.02em; color: #eef2ff; }
        h1 { font-weight: 800 !important; }
        h2 { font-weight: 700 !important; }
        p, li, span, div { color: #c5cde0; }
        [data-testid="stChatMessage"] { background: transparent !important; border: none !important; }
        .card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 12px;
        }
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.025);
            border: 1px solid rgba(255,255,255,0.07);
            padding: 14px 16px;
            border-radius: 14px;
        }
        .suggestion-btn button {
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.09) !important;
            color: #b8c2d8 !important;
            border-radius: 12px !important;
            font-size: 0.85rem !important;
            font-weight: 400 !important;
            text-align: left !important;
            padding: 12px 16px !important;
            line-height: 1.4 !important;
            height: auto !important;
            min-height: 3.5rem !important;
        }
        .suggestion-btn button:hover {
            background: rgba(255,255,255,0.08) !important;
            border-color: rgba(255,255,255,0.18) !important;
            color: #eef2ff !important;
        }
        [data-testid="stChatInput"] {
            background: #22243a !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 14px !important;
        }
        [data-testid="stChatInput"] textarea { color: #eef2ff !important; background: transparent !important; }
        [data-testid="stChatInput"] button { color: #eef2ff !important; }
        .pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.1);
            margin-right: 6px;
            margin-bottom: 6px;
            background: rgba(255,255,255,0.03);
            font-size: 0.82rem;
        }
        .muted { color: #6b7694; font-size: 0.875rem; }
        .stButton button, .stDownloadButton button { border-radius: 10px !important; font-weight: 500 !important; }
        #MainMenu { visibility: hidden; }
        footer    { visibility: hidden; }
        .src-chip {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.09);
            border-radius: 6px;
            padding: 4px 9px;
            font-size: 11px !important;
            color: #888891 !important;
            margin-right: 6px;
            margin-bottom: 5px;
        }
        .src-chips-label {
            font-size: 9.5px !important;
            color: #454550 !important;
            font-weight: 600;
            letter-spacing: 0.07em;
            margin-bottom: 6px;
            text-transform: uppercase;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_state() -> None:
    st.session_state.setdefault("db_path", "insight_ai_production.db")
    st.session_state.setdefault("last_run_id", None)
    st.session_state.setdefault("page", "Ask Questions")
    st.session_state.setdefault("chat_history", [])   # list of {role, content, sources}
    st.session_state.setdefault("ollama_ok", None)     # None=unchecked, True/False
    st.session_state.setdefault("rag_llm", None)       # cached ChatOllama instance
    st.session_state.setdefault("pending_delete", None)
    st.session_state.setdefault("_chroma_purged", False)


# ---------------------------------------------------------------------------
# RAG helpers
# ---------------------------------------------------------------------------

def _chroma_dir() -> str:
    return get_setting(st.session_state.db_path, "chroma_persist_dir", "data/chromadb") or "data/chromadb"


def _ollama_model() -> str:
    return get_setting(st.session_state.db_path, "ollama_model", "llama3.2:3b") or "llama3.2:3b"


def _check_rag() -> tuple[bool, bool]:
    """Return (chroma_available, ollama_available). Cached in session state."""
    chroma_ok = _CHROMA_AVAILABLE and _RAG_IMPORTS_OK
    if chroma_ok and st.session_state.ollama_ok is None:
        st.session_state.ollama_ok = check_ollama_status()
    ollama_ok = bool(st.session_state.ollama_ok)
    return chroma_ok, ollama_ok


def _get_llm():
    """Return a cached ChatOllama instance."""
    if st.session_state.rag_llm is None and _RAG_IMPORTS_OK:
        st.session_state.rag_llm = get_llm(model_name=_ollama_model())
    return st.session_state.rag_llm


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            "<div style='padding:14px 4px 4px;font-size:1.15rem;font-weight:700;color:#eef2ff;letter-spacing:-0.01em;'>🧠 INSIGHT.AI</div>",
            unsafe_allow_html=True,
        )
        st.caption("Document Intelligence")

        # RAG status dot
        chroma_ok, ollama_ok = _check_rag()
        if chroma_ok and ollama_ok:
            st.markdown("<span style='color:#1f9d55;font-size:0.8rem;'>● AI Ready</span>", unsafe_allow_html=True)
        elif chroma_ok and not ollama_ok:
            st.markdown("<span style='color:#d69e2e;font-size:0.8rem;'>● Keyword mode — start Ollama for AI answers</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color:#e53e3e;font-size:0.8rem;'>● RAG setup required (see Operations)</span>", unsafe_allow_html=True)

        st.divider()

        nav_items = [
            ("🏠", "Ask Questions"),
            ("📂", "Ingestion Hub"),
            ("📈", "Executive Dashboard"),
            ("🗂️", "File Explorer"),
            ("🛠️", "Operations & Recovery"),
            ("📝", "Reports and Logs"),
        ]
        for icon, name in nav_items:
            active = st.session_state.page == name
            if st.button(
                f"{icon}  {name}",
                key=f"nav_{name}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.page = name
                st.rerun()

        st.divider()
        with st.expander("⚙️ Settings"):
            st.text_input("Database path", key="db_path", label_visibility="collapsed",
                          placeholder="insight_ai_production.db")
            if st.button("Initialize / Upgrade DB", use_container_width=True):
                init_database(st.session_state.db_path)
                st.success("Database ready.")
                log_audit("initialize_database", st.session_state.db_path, "Initialized or upgraded database")

        st.caption("Mode: Premium")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

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
    st.markdown(
        f'<div class="card"><div style="font-weight:700;margin-bottom:8px;color:#eef2ff;">{title}</div><div>{body}</div></div>',
        unsafe_allow_html=True,
    )


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
            f.status, f.ocr_used, f.last_processed_at, f.llm_enriched,
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
    cur.execute(
        "SELECT file_path, error_type, error_message, created_at FROM error_logs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def load_run_history(limit: int = 50):
    conn = get_connection(st.session_state.db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, started_at, finished_at, source_type, source_value, total_files, processed_files, skipped_files, failed_files, status FROM processing_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def load_audit_logs(limit: int = 200):
    conn = get_connection(st.session_state.db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT username, role, action, target, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def summarize_dataset(records: list[dict]) -> dict:
    total_files = len(records)
    total_words = sum(r.get("word_count") or 0 for r in records)
    avg_risk = (sum(r.get("risk_score") or 0 for r in records) / total_files) if total_files else 0
    high_critical = sum(1 for r in records if (r.get("risk_label") or "") in {"High", "Critical"})
    return {"total_files": total_files, "total_words": total_words, "avg_risk": avg_risk, "high_critical": high_critical}


# ---------------------------------------------------------------------------
# Q&A: TF-IDF fallback path
# ---------------------------------------------------------------------------

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
    excerpt = next(
        (sent for sent in text.split(". ") if any(tok in sent.lower() for tok in question.lower().split()[:4])),
        text[:300],
    )
    return score, excerpt.strip()


def _run_question_tfidf(question: str) -> tuple[str, list[str]]:
    records = load_records()
    scored = []
    for rec in records:
        score, excerpt = _score_question_against_record(question, rec)
        if score > 0:
            scored.append((score, excerpt, rec))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:4]

    if not top:
        return "No strong evidence matched. Ingest some documents first via **Ingestion Hub**.", []

    top_labels = Counter((rec.get("risk_label") or "Unknown") for _, _, rec in top)
    top_types = Counter((rec.get("document_type") or "Unknown") for _, _, rec in top)
    risk_categories = Counter(cat for _, _, rec in top for cat in (rec.get("risk_categories") or []))
    flagged = Counter(flag for _, _, rec in top for flag in (rec.get("flagged_phrases") or []))
    conf = "High" if top[0][0] > 0.15 or len(top) >= 3 else "Moderate"

    answer = (
        f"Based on indexed evidence, the strongest signals are in "
        f"**{', '.join(rec.get('file_name') for _, _, rec in top[:3])}**. "
        f"Confidence: **{conf}**. "
        f"Risk levels: {', '.join(f'{k} ({v})' for k, v in top_labels.items())}. "
        f"Dominant categories: {', '.join(k for k, _ in risk_categories.most_common(4)) or 'none detected'}. "
        f"Key signals: {', '.join(k for k, _ in flagged.most_common(6)) or 'none'}. "
        f"Document types: {', '.join(f'{k} ({v})' for k, v in top_types.items())}."
    )
    sources = [rec.get("file_name", "") for _, _, rec in top if rec.get("file_name")]
    return answer, sources


# ---------------------------------------------------------------------------
# Q&A: RAG path
# ---------------------------------------------------------------------------

def _run_question_rag(question: str) -> tuple[str, list[str]] | None:
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

    return result["answer"], result["sources"]


def _run_question(question: str) -> None:
    chroma_ok, ollama_ok = _check_rag()
    now = datetime.now().strftime("%H:%M")

    st.session_state.chat_history.append({"role": "user", "content": question, "sources": [], "time": now})

    answer: str | None = None
    sources: list[str] = []

    if chroma_ok and ollama_ok:
        with st.spinner("Thinking…"):
            rag_result = _run_question_rag(question)
        if rag_result:
            answer, sources = rag_result

    if answer is None:
        tfidf_answer, tfidf_sources = _run_question_tfidf(question)
        if chroma_ok and not ollama_ok:
            answer = "⚠️ *Ollama offline — using keyword search. Start Ollama for AI-powered answers.*\n\n" + tfidf_answer
        else:
            answer = tfidf_answer
        sources = tfidf_sources

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer,
        "sources": sources,
        "time": now,
    })


# ---------------------------------------------------------------------------
# Page: Home
# ---------------------------------------------------------------------------

_HOME_SUGGESTIONS = [
    "What are the main risks management should focus on right now?",
    "Which files are the highest risk and why?",
    "Are there repeated compliance or security issues across the dataset?",
    "What opportunities for improvement appear across these documents?",
]


# ---------------------------------------------------------------------------
# Page: Ingestion Hub
# ---------------------------------------------------------------------------

def render_ingestion() -> None:
    log_audit("open_page", "Ingestion Hub", "Opened page Ingestion Hub")
    st.title("📂 Ingestion Hub")
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
                run_id = process_uploaded_files_to_db(
                    uploads, st.session_state.db_path, mode="Premium", progress_callback=update_up
                )
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
                progress = st.progress(0, text="Preparing folder scan…")
                def update_fo(done, total, message):
                    pct = int((done / max(total, 1)) * 100)
                    progress.progress(min(pct, 100), text=message)
                run_id = process_folder_to_db(
                    folder_path.strip(), st.session_state.db_path, mode="Premium",
                    recursive=recursive, progress_callback=update_fo,
                )
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


# ---------------------------------------------------------------------------
# Page: Executive Dashboard
# ---------------------------------------------------------------------------

def render_dashboard() -> None:
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
        st.markdown(
            f"""
            <div class='card'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div><b style='color:#eef2ff;'>{row.get('file_name')}</b></div>
                    <div style='color:{color};font-weight:700;'>{label} ({row.get('risk_score') or 0})</div>
                </div>
                <div class='muted'>{row.get('file_path')}</div>
                <div style='margin-top:8px;'><b>Type:</b> {row.get('document_type') or 'Unknown'}</div>
                <div style='margin-top:6px;'><b>Management takeaway:</b> {row.get('management_takeaway') or 'No takeaway available.'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Page: File Explorer
# ---------------------------------------------------------------------------

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
                        st.markdown(f"- **{name}** — `{path}`")


# ---------------------------------------------------------------------------
# Page: Ask Questions
# ---------------------------------------------------------------------------

def _source_chips_html(sources: list[str]) -> str:
    if not sources:
        return ""
    chips = "".join(f'<span class="src-chip">{fname}</span>' for fname in sources)
    return (
        '<div style="margin-top:10px;padding-left:2px;">'
        '<div class="src-chips-label">SOURCES</div>'
        f'{chips}</div>'
    )


def render_questions() -> None:
    log_audit("open_page", "Ask Questions", "Opened page Ask Questions")

    if get_setting(st.session_state.db_path, "health_check_any_failed", "0") == "1":
        st.warning(
            "Setup incomplete — some components failed the last health check. "
            "Go to **Operations → Setup Health Check** to fix them.",
            icon="⚠️",
        )

    _check_rag()

    messages = st.session_state.chat_history

    if not messages:
        st.markdown(
            """
            <div style="
                display:flex;flex-direction:column;align-items:center;
                justify-content:center;min-height:52vh;text-align:center;
                padding:2rem 1rem 1.5rem;
            ">
                <div style="font-size:2.6rem;font-weight:800;letter-spacing:-0.03em;color:#eef2ff;margin-bottom:0.6rem;">
                    INSIGHT.AI
                </div>
                <div style="color:#6b7694;font-size:1.05rem;">
                    What would you like to know about your documents?
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2, gap="small")
        for i, s in enumerate(_HOME_SUGGESTIONS):
            with (c1 if i % 2 == 0 else c2):
                st.markdown('<div class="suggestion-btn">', unsafe_allow_html=True)
                if st.button(s, key=f"q_{i}", use_container_width=True):
                    log_audit("ask_question", "Ask Questions", s)
                    _run_question(s)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        for msg in messages:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
                    sources = msg.get("sources") or []
                    if sources:
                        st.markdown(_source_chips_html(sources), unsafe_allow_html=True)

    if prompt := st.chat_input("Ask anything about your documents…"):
        log_audit("ask_question", "Ask Questions", prompt)
        _run_question(prompt)
        st.rerun()


# ---------------------------------------------------------------------------
# Page: Operations & Recovery
# ---------------------------------------------------------------------------

def render_operations() -> None:
    log_audit("open_page", "Operations", "Opened page Operations")
    st.title("🛠️ Operations, Scheduling, Backup and Validation")
    tabs = st.tabs(["Scheduled scans", "Backup & recovery", "OCR diagnostics", "Validation metrics", "AI / RAG Settings", "Setup Health Check"])

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
        status = ocr_status()
        st.markdown("### OCR runtime diagnostics")
        c1, c2, c3 = st.columns(3)
        c1.metric("pytesseract", "Available" if status["pytesseract"] else "Missing")
        c2.metric("pdf2image", "Available" if status["pdf2image"] else "Missing")
        c3.metric("OCR ready", "Yes" if status["available"] else "No")
        st.info("Full OCR requires native Tesseract OCR and Poppler installed on the host machine.")
        enabled = st.checkbox("Enable OCR fallback", value=get_setting(st.session_state.db_path, "ocr_enabled", "1") == "1")
        page_limit = st.number_input("OCR page limit per PDF", min_value=1, max_value=200, value=int(get_setting(st.session_state.db_path, "ocr_page_limit", "30")))
        dpi = st.number_input("OCR DPI", min_value=100, max_value=400, value=int(get_setting(st.session_state.db_path, "ocr_dpi", "220")))
        min_words = st.number_input("Min words before OCR fallback", min_value=1, max_value=500, value=int(get_setting(st.session_state.db_path, "ocr_min_words_threshold", "30")))
        if st.button("Save OCR settings"):
            set_setting(st.session_state.db_path, "ocr_enabled", "1" if enabled else "0")
            set_setting(st.session_state.db_path, "ocr_page_limit", str(page_limit))
            set_setting(st.session_state.db_path, "ocr_dpi", str(dpi))
            set_setting(st.session_state.db_path, "ocr_min_words_threshold", str(min_words))
            st.success("OCR settings saved.")

    with tabs[3]:
        st.markdown("### Validation against labeled internal dataset")
        st.write("Upload a CSV with columns: `file_name`, optional `expected_risk_label`, optional `expected_document_type`.")
        val_file = st.file_uploader("Upload validation CSV", type=["csv"], key="val_csv")
        if val_file is not None:
            val_df = pd.read_csv(val_file)
            st.dataframe(val_df.head(20), use_container_width=True, hide_index=True)
            if st.button("Run validation"):
                records = {r["file_name"]: r for r in load_records()}
                total = matched = risk_ok = doc_ok = 0
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
                    risk_match = (
                        str(row.get("expected_risk_label", "")).strip().lower()
                        == str(rec.get("risk_label", "")).strip().lower()
                        if pd.notna(row.get("expected_risk_label")) and str(row.get("expected_risk_label", "")).strip()
                        else None
                    )
                    doc_match = (
                        str(row.get("expected_document_type", "")).strip().lower()
                        == str(rec.get("document_type", "")).strip().lower()
                        if pd.notna(row.get("expected_document_type")) and str(row.get("expected_document_type", "")).strip()
                        else None
                    )
                    if risk_match is True:
                        risk_ok += 1
                    if doc_match is True:
                        doc_ok += 1
                    details.append([fname, row.get("expected_risk_label"), rec.get("risk_label"),
                                     row.get("expected_document_type"), rec.get("document_type"),
                                     1 if ((risk_match is True) or (doc_match is True)) else 0])
                risk_acc = (risk_ok / max(sum(1 for x in val_df.get("expected_risk_label", []) if pd.notna(x) and str(x).strip()), 1)) * 100 if "expected_risk_label" in val_df.columns else 0
                doc_acc = (doc_ok / max(sum(1 for x in val_df.get("expected_document_type", []) if pd.notna(x) and str(x).strip()), 1)) * 100 if "expected_document_type" in val_df.columns else 0
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Rows", total)
                c2.metric("Matched", matched)
                c3.metric("Risk accuracy", f"{risk_acc:.1f}%")
                c4.metric("Doc type accuracy", f"{doc_acc:.1f}%")
                st.dataframe(
                    pd.DataFrame(details, columns=["file_name", "expected_risk_label", "predicted_risk_label",
                                                   "expected_document_type", "predicted_document_type", "matched"]),
                    use_container_width=True, hide_index=True,
                )

    with tabs[4]:
        st.markdown("### AI / RAG Settings")

        if not _RAG_IMPORTS_OK:
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
            set_setting(st.session_state.db_path, "ollama_model", new_model.strip())
            set_setting(st.session_state.db_path, "chroma_persist_dir", new_chroma.strip())
            st.session_state.rag_llm = None   # force LLM re-init
            st.session_state.ollama_ok = None
            st.success("RAG settings saved.")

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

        st.divider()
        st.markdown("### Ollama setup instructions")
        st.info(
            "Ollama is not a Python package — it has its own Windows installer.\n\n"
            "1. Download and install Ollama from **ollama.com**\n"
            "2. Open a terminal and run: `ollama pull llama3.2:3b`\n"
            "3. Ollama runs as a background service on `localhost:11434`\n"
            "4. Refresh this page — the status dot in the sidebar will turn green."
        )

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


# ---------------------------------------------------------------------------
# Page: Reports and Logs
# ---------------------------------------------------------------------------

def render_reports() -> None:
    log_audit("open_page", "Reports and Logs", "Opened page Reports and Logs")
    st.title("📝 Reports and Logs")
    records = load_records()
    txt = build_export_text_from_records(records)
    js = build_export_json_from_records(records)
    c1, c2 = st.columns(2)
    with c1:
        if st.download_button("Download TXT Executive Report", txt, file_name="insight_ai_report.txt", mime="text/plain", use_container_width=True):
            log_audit("download_report", "TXT", "Downloaded TXT report")
    with c2:
        if st.download_button("Download JSON Executive Report", js, file_name="insight_ai_report.json", mime="application/json", use_container_width=True):
            log_audit("download_report", "JSON", "Downloaded JSON report")
    st.markdown("### Processing run history")
    st.dataframe(pd.DataFrame(load_run_history()), use_container_width=True, hide_index=True)
    st.markdown("### Error log")
    errors = load_errors()
    if errors:
        st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)
    else:
        st.success("No errors logged.")
    st.markdown("### Audit log")
    st.dataframe(pd.DataFrame(load_audit_logs()), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    inject_css()
    init_state()
    render_sidebar()
    init_database(st.session_state.db_path)
    if _RAG_IMPORTS_OK and _CHROMA_AVAILABLE and not st.session_state._chroma_purged:
        st.session_state._chroma_purged = True
        purge_orphaned_chunks(st.session_state.db_path, persist_dir=_chroma_dir())

    page = st.session_state.page
    if page == "Ask Questions":
        render_questions()
    elif page == "Ingestion Hub":
        render_ingestion()
    elif page == "Executive Dashboard":
        render_dashboard()
    elif page == "File Explorer":
        render_file_explorer()
    elif page == "Operations & Recovery":
        render_operations()
    elif page == "Reports and Logs":
        render_reports()


if __name__ == "__main__":
    main()
