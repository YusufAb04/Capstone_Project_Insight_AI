from __future__ import annotations

import streamlit as st

from src.database import get_setting
from src.ui.helpers import log_audit
from src.ui.qa import _HOME_SUGGESTIONS, _run_question, _source_chips_html
from src.ui.rag_helpers import _check_rag


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
                    error_type = msg.get("error_type")
                    if error_type == "no_chunks":
                        st.error("No searchable content found. This file has 0 chunks — go to Ingestion Hub and re-ingest it.")
                    elif error_type == "low_similarity":
                        st.warning("Found content but nothing closely matched your question. Try rephrasing or ask about a specific section.")
                    elif error_type == "ollama_timeout":
                        st.error("Ollama took too long to respond. Check it's running: open a terminal and run `ollama serve`.")
                    else:
                        st.markdown(msg["content"])
                    sources = msg.get("sources") or []
                    if sources:
                        st.markdown(_source_chips_html(sources), unsafe_allow_html=True)

    if prompt := st.chat_input("Ask anything about your documents…"):
        log_audit("ask_question", "Ask Questions", prompt)
        _run_question(prompt)
        st.rerun()
