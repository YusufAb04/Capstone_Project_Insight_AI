from __future__ import annotations

import streamlit as st

from src.database import init_database
from src.ui.helpers import log_audit
from src.ui.rag_helpers import _check_rag


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            "<div style='padding:14px 4px 4px;font-size:1.15rem;font-weight:700;color:#eef2ff;letter-spacing:-0.01em;'> INSIGHT.AI</div>",
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
            ("", "Ask Questions"),
            ("", "Ingestion Hub"),
            ("", "Executive Dashboard"),
            ("", "File Explorer"),
            ("", "Operations & Recovery"),
            ("", "Reports and Logs"),
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
