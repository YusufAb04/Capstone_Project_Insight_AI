from __future__ import annotations

import streamlit as st

from src.database import get_setting
from src.ui.deps import CHROMA_AVAILABLE, RAG_IMPORTS_OK, check_ollama_status, get_llm


def _chroma_dir() -> str:
    return get_setting(st.session_state.db_path, "chroma_persist_dir", "data/chromadb") or "data/chromadb"


def _ollama_model() -> str:
    return get_setting(st.session_state.db_path, "ollama_model", "llama3.2:3b") or "llama3.2:3b"


def _check_rag() -> tuple[bool, bool]:
    """Return (chroma_available, ollama_available). Cached in session state."""
    chroma_ok = CHROMA_AVAILABLE and RAG_IMPORTS_OK
    if chroma_ok and st.session_state.ollama_ok is None:
        st.session_state.ollama_ok = check_ollama_status()
    ollama_ok = bool(st.session_state.ollama_ok)
    return chroma_ok, ollama_ok


def _get_llm():
    """Return a cached ChatOllama instance."""
    if st.session_state.rag_llm is None and RAG_IMPORTS_OK:
        st.session_state.rag_llm = get_llm(model_name=_ollama_model())
    return st.session_state.rag_llm
