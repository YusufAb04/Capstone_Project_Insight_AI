from __future__ import annotations

from src.database import get_connection


def find_duplicates(db_path: str) -> list[dict]:
    """Return groups of files that share the same SHA-256 hash.

    Each entry in the returned list represents one duplicate group:
        file_hash  — the shared SHA-256 hash
        count      — number of files with this hash
        file_paths — list of file paths
        file_names — list of file names
    """
    conn = get_connection(db_path)
    cur = conn.cursor()

    # Find hashes that appear more than once (excluding empty/upload hashes)
    cur.execute(
        """
        SELECT file_hash, COUNT(*) as cnt
        FROM files
        WHERE file_hash != '' AND file_hash != 'uploaded-session' AND status = 'processed'
        GROUP BY file_hash
        HAVING cnt > 1
        """
    )
    dup_hashes = [row[0] for row in cur.fetchall()]

    groups = []
    for h in dup_hashes:
        cur.execute(
            "SELECT file_path, file_name FROM files WHERE file_hash = ?",
            (h,),
        )
        rows = cur.fetchall()
        groups.append({
            "file_hash": h,
            "count": len(rows),
            "file_paths": [r[0] for r in rows],
            "file_names": [r[1] for r in rows],
        })

    conn.close()
    return groups


def check_file_for_duplicate(db_path: str, file_hash: str, current_file_path: str) -> list[str]:
    """Return paths of other files that have the same hash as *file_hash*.

    Used during ingestion to warn about newly detected duplicates.
    Returns an empty list if no duplicates exist.
    """
    if not file_hash or file_hash == "uploaded-session":
        return []

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT file_path FROM files WHERE file_hash = ? AND file_path != ? AND status = 'processed'",
        (file_hash, current_file_path),
    )
    matches = [row[0] for row in cur.fetchall()]
    conn.close()
    return matches
