from __future__ import annotations

import streamlit as st


def init_state() -> None:
    st.session_state.setdefault("db_path", "insight_ai_production.db")
    st.session_state.setdefault("last_run_id", None)
    st.session_state.setdefault("last_excluded", [])
    st.session_state.setdefault("page", "Ask Questions")
    st.session_state.setdefault("chat_history", [])   # list of {role, content, sources}
    st.session_state.setdefault("ollama_ok", None)     # None=unchecked, True/False
    st.session_state.setdefault("rag_llm", None)       # cached ChatOllama instance
    st.session_state.setdefault("pending_delete", None)
    st.session_state.setdefault("pending_dup_delete", None)
    st.session_state.setdefault("_chroma_purged", False)
