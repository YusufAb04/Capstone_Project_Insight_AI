from __future__ import annotations

import pandas as pd
import streamlit as st

from src.exporter import build_export_json_from_records, build_export_text_from_records
from src.ui.helpers import load_audit_logs, load_errors, load_records, load_run_history, log_audit


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
