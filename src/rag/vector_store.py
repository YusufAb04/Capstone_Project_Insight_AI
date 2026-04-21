from __future__ import annotations

# Import the rag package first so the pysqlite3 patch is applied before
# chromadb is loaded.
import src.rag  # noqa: F401

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

_COLLECTION_NAME = "insight_documents"
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Module-level singleton so the client is only created once per process.
_client: chromadb.PersistentClient | None = None
_collection = None
_current_persist_dir: str | None = None


def _get_embedding_fn():
    return SentenceTransformerEmbeddingFunction(model_name=_EMBEDDING_MODEL)


def get_collection(persist_dir: str = "data/chromadb"):
    """Return (and lazily create) the ChromaDB collection singleton."""
    global _client, _collection, _current_persist_dir

    if _client is None or _current_persist_dir != persist_dir:
        _client = chromadb.PersistentClient(path=persist_dir)
        _current_persist_dir = persist_dir
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=_get_embedding_fn(),
            metadata={"hnsw:space": "cosine"},
        )

    return _collection


def upsert_document(chunks: list[dict], persist_dir: str = "data/chromadb") -> int:
    """Embed and store *chunks* in ChromaDB. Returns number of chunks written."""
    if not chunks:
        return 0

    collection = get_collection(persist_dir)
    collection.upsert(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )
    return len(chunks)


def delete_by_file_path(file_path: str, persist_dir: str = "data/chromadb") -> int:
    """Delete all chunks that belong to *file_path*. Returns number deleted.

    Uses pagination to handle ChromaDB 1.x's default per-call result limit,
    ensuring all chunks are found and deleted even for large documents.
    """
    collection = get_collection(persist_dir)
    all_ids = []
    batch_size = 500
    offset = 0

    while True:
        results = collection.get(
            where={"file_path": file_path},
            limit=batch_size,
            offset=offset,
            include=[],   # IDs only — fastest possible fetch
        )
        batch_ids = results["ids"] if isinstance(results, dict) else list(results.ids)
        if not batch_ids:
            break
        all_ids.extend(batch_ids)
        if len(batch_ids) < batch_size:
            break
        offset += batch_size

    if all_ids:
        collection.delete(ids=all_ids)
    return len(all_ids)


def similarity_search(query: str, top_k: int = 4, persist_dir: str = "data/chromadb") -> list[dict]:
    """Return the top-k most relevant chunks for *query*.

    Each result dict has keys: id, text, metadata, distance.
    """
    collection = get_collection(persist_dir)
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results and results.get("ids"):
        for i, chunk_id in enumerate(results["ids"][0]):
            chunks.append({
                "id": chunk_id,
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
    return chunks


def collection_stats(persist_dir: str = "data/chromadb") -> dict:
    """Return basic stats about the ChromaDB collection."""
    try:
        collection = get_collection(persist_dir)
        count = collection.count()
        return {"chunk_count": count, "collection": _COLLECTION_NAME, "status": "ok"}
    except Exception as exc:
        return {"chunk_count": 0, "collection": _COLLECTION_NAME, "status": str(exc)}


def reset_collection(persist_dir: str = "data/chromadb") -> None:
    """Delete and recreate the collection (destructive — wipes all embeddings)."""
    global _client, _collection

    col = get_collection(persist_dir)
    _client.delete_collection(_COLLECTION_NAME)
    _collection = _client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_get_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )
