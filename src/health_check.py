from __future__ import annotations

import gc
import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Literal

import requests

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer
except ImportError:
    _SentenceTransformer = None

try:
    import chromadb as _chromadb
except ImportError:
    _chromadb = None

Status = Literal["ok", "warn", "fail"]

_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_EXPECTED_DIMS = 384
_CLOUD_SYNC_MARKERS = ("onedrive", "google drive", "dropbox", "icloud drive")


@dataclass
class CheckResult:
    name: str
    status: Status
    message: str
    fix: str = ""


def check_embedding_model() -> CheckResult:
    if _SentenceTransformer is None:
        return CheckResult(
            name="Embedding model",
            status="fail",
            message="sentence-transformers is not installed.",
            fix="Run: pip install sentence-transformers==5.4.1",
        )
    try:
        model = _SentenceTransformer(_EMBEDDING_MODEL)
        embedding = model.encode("test sentence")
        if len(embedding) != _EXPECTED_DIMS:
            return CheckResult(
                name="Embedding model",
                status="fail",
                message=f"Expected {_EXPECTED_DIMS} dimensions, got {len(embedding)}. Model may be corrupted.",
                fix="Delete the cached model folder in ~/.cache/huggingface and restart the app to re-download.",
            )
        return CheckResult(
            name="Embedding model",
            status="ok",
            message=f"{_EMBEDDING_MODEL} loaded — producing valid {_EXPECTED_DIMS}-dim embeddings.",
        )
    except Exception as exc:
        return CheckResult(
            name="Embedding model",
            status="fail",
            message=f"Failed to load: {exc}",
            fix="Run: pip install sentence-transformers==5.4.1",
        )


def check_chromadb(persist_dir: str) -> CheckResult:
    if _chromadb is None:
        return CheckResult(
            name="ChromaDB vector store",
            status="fail",
            message="chromadb is not installed.",
            fix="Run: pip install chromadb==0.5.23",
        )
    tmp = None
    try:
        import src.rag  # ensure pysqlite3 patch is applied before chromadb opens any db
        tmp = tempfile.mkdtemp()
        client = _chromadb.PersistentClient(path=tmp)
        col = client.get_or_create_collection("_health_test")
        col.upsert(ids=["probe"], documents=["health check"], metadatas=[{"source": "health"}])
        result = col.get(ids=["probe"])
        if not result["ids"]:
            raise RuntimeError("Write/read cycle produced no results")
        # Explicitly release file handles before temp dir removal — on Windows,
        # ChromaDB keeps chroma.sqlite3 locked until the client is GC'd.
        del col, client
        gc.collect()

        chunk_count = 0
        try:
            real_client = _chromadb.PersistentClient(path=persist_dir)
            real_col = real_client.get_or_create_collection("insight_documents")
            chunk_count = real_col.count()
            del real_col, real_client
            gc.collect()
        except Exception:
            pass
        return CheckResult(
            name="ChromaDB vector store",
            status="ok",
            message=f"Writable. pysqlite3 patch active. {chunk_count} chunks currently indexed.",
        )
    except Exception as exc:
        return CheckResult(
            name="ChromaDB vector store",
            status="fail",
            message=f"ChromaDB error: {exc}",
            fix="Run: pip install chromadb==0.5.23 pysqlite3-binary. Ensure the data/ folder is writable.",
        )
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def check_ollama(base_url: str = "http://localhost:11434", model: str = "llama3.2:3b") -> CheckResult:
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=3)
        if resp.status_code != 200:
            return CheckResult(
                name="Ollama LLM",
                status="fail",
                message=f"Ollama responded with HTTP {resp.status_code}.",
                fix="Open a terminal and run: ollama serve",
            )
        models = [m["name"] for m in resp.json().get("models", [])]
        model_base = model.split(":")[0]
        if not any(model_base in m for m in models):
            return CheckResult(
                name="Ollama LLM",
                status="warn",
                message=f"Ollama is running but model '{model}' is not pulled.",
                fix=f"Open a terminal and run: ollama pull {model}",
            )
        return CheckResult(
            name="Ollama LLM",
            status="ok",
            message=f"Ollama running. Model '{model}' is available.",
        )
    except requests.exceptions.Timeout:
        return CheckResult(
            name="Ollama LLM",
            status="warn",
            message="Ollama is running but did not respond within 3 seconds.",
            fix="Ollama may still be loading a model. Wait 10 seconds and run checks again.",
        )
    except requests.exceptions.ConnectionError:
        return CheckResult(
            name="Ollama LLM",
            status="fail",
            message="Ollama is not running.",
            fix="Open a terminal and run: ollama serve  (or launch the Ollama desktop app)",
        )
    except Exception as exc:
        return CheckResult(
            name="Ollama LLM",
            status="fail",
            message=f"Could not reach Ollama: {exc}",
            fix="Open a terminal and run: ollama serve",
        )


def check_disk(data_dir: str) -> CheckResult:
    resolved = os.path.abspath(data_dir).lower()
    for marker in _CLOUD_SYNC_MARKERS:
        if marker in resolved:
            return CheckResult(
                name="Disk / database",
                status="warn",
                message=f"Project appears to be inside a cloud-sync folder ({marker.title()}).",
                fix="Move the project to a local path like C:\\Projects\\INSIGHT_AI. Cloud sync can lock and corrupt ChromaDB files.",
            )
    try:
        os.makedirs(data_dir, exist_ok=True)
        test_file = os.path.join(data_dir, "_write_test.tmp")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return CheckResult(
            name="Disk / database",
            status="ok",
            message=f"Data directory is writable: {data_dir}",
        )
    except Exception as exc:
        return CheckResult(
            name="Disk / database",
            status="fail",
            message=f"Cannot write to data directory: {exc}",
            fix="Check folder permissions or move the project to a local path.",
        )


def run_all_checks(persist_dir: str, base_url: str, model: str, data_dir: str) -> list[CheckResult]:
    return [
        check_embedding_model(),
        check_chromadb(persist_dir),
        check_ollama(base_url, model),
        check_disk(data_dir),
    ]
