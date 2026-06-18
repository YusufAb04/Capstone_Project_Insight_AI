from __future__ import annotations

from src.rag.llm_interface import check_ollama_status
from src.rag.vector_store import collection_stats


def rag_health_report(persist_dir: str = "data/chromadb", ollama_model: str = "llama3.2:3b") -> dict:
    """Return a dict describing the health of every RAG component."""
    report: dict = {}

    # --- ChromaDB ---
    try:
        import chromadb  # noqa: F401
        report["chromadb_installed"] = True
    except ImportError:
        report["chromadb_installed"] = False

    try:
        stats = collection_stats(persist_dir)
        report["chromadb_collection_ok"] = stats["status"] == "ok"
        report["chunk_count"] = stats["chunk_count"]
    except Exception as exc:
        report["chromadb_collection_ok"] = False
        report["chunk_count"] = 0
        report["chromadb_error"] = str(exc)

    # --- Embedding model ---
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        report["embedding_model_installed"] = True
    except ImportError:
        report["embedding_model_installed"] = False

    # --- Ollama ---
    report["ollama_reachable"] = check_ollama_status()
    report["ollama_model"] = ollama_model

    if report["ollama_reachable"]:
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            data = resp.json()
            loaded = [m["name"] for m in data.get("models", [])]
            report["ollama_model_loaded"] = any(ollama_model in m for m in loaded)
            report["ollama_available_models"] = loaded
        except Exception:
            report["ollama_model_loaded"] = False
            report["ollama_available_models"] = []
    else:
        report["ollama_model_loaded"] = False
        report["ollama_available_models"] = []

    # --- Overall readiness ---
    report["rag_ready"] = (
        report.get("chromadb_installed", False)
        and report.get("chromadb_collection_ok", False)
        and report.get("ollama_reachable", False)
    )

    return report
