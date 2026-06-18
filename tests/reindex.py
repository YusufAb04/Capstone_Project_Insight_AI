"""
Re-index all documents in ChromaDB using the updated chunker settings.
Reads content_text from analysis_results (no original files needed).
Run: python tests/reindex.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sqlite3
from src.rag.chunker import chunk_text
from src.rag.vector_store import upsert_document, delete_by_file_path

DB_PATH    = "insight_ai_production.db"
CHROMA_DIR = "data/chromadb"


def reindex_all():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT f.id, f.file_path, f.file_name, a.content_text
        FROM files f
        JOIN analysis_results a ON a.file_id = f.id
        WHERE f.chroma_synced = 1 AND f.status = 'processed'
    """)
    rows = cur.fetchall()

    print(f"Re-indexing {len(rows)} document(s) with new chunk settings (500 chars, table-aware)...\n")

    for row in rows:
        file_path  = row["file_path"]
        file_name  = row["file_name"]
        content    = row["content_text"] or ""

        if not content.strip():
            print(f"  SKIP  {file_name} — no content_text stored")
            continue

        chunks = chunk_text(content, file_path=file_path, file_name=file_name)
        delete_by_file_path(file_path, persist_dir=CHROMA_DIR)
        upsert_document(chunks, persist_dir=CHROMA_DIR)

        conn.execute(
            "UPDATE files SET chunk_count = ? WHERE id = ?",
            (len(chunks), row["id"]),
        )
        conn.commit()

        print(f"  OK    {file_name} — {len(chunks)} chunks (was {row['id']})")

    conn.close()
    print("\nRe-index complete.")


if __name__ == "__main__":
    reindex_all()
