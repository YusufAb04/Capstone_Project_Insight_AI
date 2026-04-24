from __future__ import annotations

# Import the rag package first so the pysqlite3 patch is applied before
# chromadb is loaded.
import src.rag  # noqa: F401

import json
import os
import shutil
import sqlite3

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


def _migrate_chroma_config(persist_dir: str) -> None:
    """Patch any collection rows whose config_json_str is missing '_type'.

    ChromaDB ≥ 0.5 requires every collection config to carry a '_type'
    discriminator. Databases created by older versions stored '{}', which
    causes a KeyError when the newer client tries to deserialise the config.
    We fix it in-place against the SQLite file so no embeddings are lost.
    """
    db_file = os.path.join(persist_dir, "chroma.sqlite3")
    if not os.path.isfile(db_file):
        return
    try:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("SELECT id, config_json_str FROM collections")
        rows = cur.fetchall()
        for cid, config_str in rows:
            config = json.loads(config_str) if config_str else {}
            if "_type" in config:
                continue
            cur.execute(
                "SELECT key, str_value FROM collection_metadata WHERE collection_id = ?",
                (cid,),
            )
            meta = dict(cur.fetchall())
            space = meta.get("hnsw:space", "l2")
            new_config = {
                "_type": "CollectionConfigurationInternal",
                "hnsw_configuration": {
                    "_type": "HNSWConfigurationInternal",
                    "space": space,
                    "ef_construction": 100,
                    "ef_search": 10,
                    "num_threads": os.cpu_count() or 4,
                    "M": 16,
                    "resize_factor": 1.2,
                    "batch_size": 100,
                    "sync_threshold": 1000,
                },
            }
            cur.execute(
                "UPDATE collections SET config_json_str = ? WHERE id = ?",
                (json.dumps(new_config), cid),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass  # migration is best-effort; let ChromaDB surface the real error


def get_collection(persist_dir: str = "data/chromadb"):
    """Return (and lazily create) the ChromaDB collection singleton."""
    global _client, _collection, _current_persist_dir

    if _client is None or _current_persist_dir != persist_dir or _collection is None:
        _migrate_chroma_config(persist_dir)
        try:
            _client = chromadb.PersistentClient(path=persist_dir)
            _current_persist_dir = persist_dir
            _collection = _client.get_or_create_collection(
                name=_COLLECTION_NAME,
                embedding_function=_get_embedding_fn(),
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            # Roll back so the next call retries rather than returning None.
            _client = None
            _current_persist_dir = None
            _collection = None
            raise

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


def similarity_search(query: str, top_k: int = 8, persist_dir: str = "data/chromadb") -> list[dict]:
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
    global _client, _collection, _current_persist_dir

    # Release the client before touching the filesystem.
    _client = None
    _collection = None
    _current_persist_dir = None

    # ChromaDB's delete_collection API raises KeyError: '_type' when the stored
    # config JSON was written by an older version that omitted that field.
    # Wiping the persist directory bypasses the broken API entirely.
    if os.path.isdir(persist_dir):
        shutil.rmtree(persist_dir)
    os.makedirs(persist_dir, exist_ok=True)

    get_collection(persist_dir)


def purge_orphaned_chunks(db_path: str, persist_dir: str = "data/chromadb") -> int:
    """Delete ChromaDB chunks whose file_path no longer exists in the SQLite files table.

    Called once per session on app startup to clean up chunks left behind by
    files that were deleted before per-row ChromaDB cleanup was introduced.
    Returns the number of chunks removed.
    """
    try:
        collection = get_collection(persist_dir)
        chroma_paths: set[str] = set()
        batch_size = 1000
        offset = 0
        while True:
            results = collection.get(limit=batch_size, offset=offset, include=["metadatas"])
            ids = results.get("ids", [])
            if not ids:
                break
            for meta in results.get("metadatas", []):
                fp = (meta or {}).get("file_path")
                if fp:
                    chroma_paths.add(fp)
            if len(ids) < batch_size:
                break
            offset += batch_size

        if not chroma_paths:
            return 0

        conn = sqlite3.connect(db_path)
        try:
            placeholders = ",".join("?" * len(chroma_paths))
            sqlite_paths = {
                row[0]
                for row in conn.execute(
                    f"SELECT file_path FROM files WHERE file_path IN ({placeholders})",
                    list(chroma_paths),
                ).fetchall()
            }
        finally:
            conn.close()

        total = 0
        for fp in chroma_paths - sqlite_paths:
            total += delete_by_file_path(fp, persist_dir)
        return total
    except Exception:
        return 0
