from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from src.database import get_connection


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
