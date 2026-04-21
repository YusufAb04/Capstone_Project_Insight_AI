from __future__ import annotations

import hashlib

from langchain_text_splitters import RecursiveCharacterTextSplitter

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=75,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _file_id_prefix(file_path: str) -> str:
    """Short deterministic prefix derived from the file path."""
    return hashlib.sha256(file_path.encode()).hexdigest()[:16]


def chunk_text(text: str, file_path: str, file_name: str) -> list[dict]:
    """Split *text* into overlapping chunks ready for embedding.

    Returns a list of dicts with keys:
        id       — deterministic chunk ID (stable across re-ingestion)
        text     — chunk content
        metadata — dict with file_path, file_name, chunk_index, total_chunks
    """
    if not text or not text.strip():
        return []

    raw_chunks = _SPLITTER.split_text(text)
    prefix = _file_id_prefix(file_path)
    total = len(raw_chunks)

    return [
        {
            "id": f"{prefix}::chunk_{i}",
            "text": chunk,
            "metadata": {
                "file_path": file_path,
                "file_name": file_name,
                "chunk_index": i,
                "total_chunks": total,
            },
        }
        for i, chunk in enumerate(raw_chunks)
    ]
