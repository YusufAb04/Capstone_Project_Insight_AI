from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui.helpers import load_records, log_audit, risk_color, summarize_dataset


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
