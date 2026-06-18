"""Centralized optional/feature imports shared across the UI package.

Importing these in one place keeps the try/except fallback logic out of
every page module.
"""
from __future__ import annotations

from src.batch_processor import _CHROMA_AVAILABLE as CHROMA_AVAILABLE

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None

try:
    from src.rag.llm_interface import check_ollama_status, get_llm, ask_with_rag
    from src.rag.vector_store import collection_stats, purge_orphaned_chunks, delete_by_file_path
    from src.rag.health import rag_health_report
    RAG_IMPORTS_OK = True
except ImportError:
    RAG_IMPORTS_OK = False
    check_ollama_status = get_llm = ask_with_rag = None
    collection_stats = purge_orphaned_chunks = delete_by_file_path = None
    rag_health_report = None

try:
    from src.health_check import run_all_checks, CheckResult
    HEALTH_CHECK_AVAILABLE = True
except ImportError:
    HEALTH_CHECK_AVAILABLE = False
    run_all_checks = CheckResult = None
