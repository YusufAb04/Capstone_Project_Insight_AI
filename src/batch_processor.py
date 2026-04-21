from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Callable, Optional

from src.database import init_database, get_connection, get_setting
from src.folder_ingestion import scan_folder, compute_file_hash
from src.file_processor import process_file_path, process_uploaded_file

ProgressCallback = Optional[Callable[[int, int, str], None]]

# RAG stack is optional — app runs without it if packages aren't installed
try:
    from src.rag.chunker import chunk_text
    from src.rag.vector_store import upsert_document, delete_by_file_path
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_ocr_config(db_path: str) -> dict:
    return {
        "ocr_enabled": get_setting(db_path, "ocr_enabled", "1") == "1",
        "ocr_page_limit": int(get_setting(db_path, "ocr_page_limit", "30") or 30),
        "ocr_dpi": int(get_setting(db_path, "ocr_dpi", "220") or 220),
        "ocr_min_words_threshold": int(get_setting(db_path, "ocr_min_words_threshold", "30") or 30),
    }


def _load_chroma_dir(db_path: str) -> str:
    return get_setting(db_path, "chroma_persist_dir", "data/chromadb") or "data/chromadb"


def create_run(conn, source_type: str, source_value: str, total_files: int) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO processing_runs
        (started_at, source_type, source_value, total_files, processed_files, skipped_files, failed_files, status)
        VALUES (?, ?, ?, ?, 0, 0, 0, 'running')
        """,
        (now_str(), source_type, source_value, total_files),
    )
    conn.commit()
    return cur.lastrowid


def finalize_run(conn, run_id: int, processed: int, skipped: int, failed: int, status: str = "completed") -> None:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE processing_runs
        SET finished_at = ?, processed_files = ?, skipped_files = ?, failed_files = ?, status = ?
        WHERE id = ?
        """,
        (now_str(), processed, skipped, failed, status, run_id),
    )
    conn.commit()


def log_error(conn, file_path: str, error_type: str, error_message: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO error_logs (file_path, error_type, error_message, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (file_path, error_type, error_message[:2000], now_str()),
    )
    conn.commit()


def upsert_file_record(
    conn,
    *,
    file_path: str,
    file_name: str,
    extension: str,
    file_size: int,
    modified_time: float,
    file_hash: str,
    status: str,
    ocr_used: bool,
    chroma_synced: int = 0,
    chunk_count: int = 0,
) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM files WHERE file_path = ?", (file_path,))
    row = cur.fetchone()
    if row:
        file_id = row[0]
        cur.execute(
            """
            UPDATE files
            SET file_name = ?, extension = ?, file_size = ?, modified_time = ?, file_hash = ?,
                status = ?, ocr_used = ?, last_processed_at = ?, chroma_synced = ?, chunk_count = ?
            WHERE id = ?
            """,
            (file_name, extension, file_size, modified_time, file_hash, status,
             int(bool(ocr_used)), now_str(), chroma_synced, chunk_count, file_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO files
            (file_path, file_name, extension, file_size, modified_time, file_hash,
             status, ocr_used, last_processed_at, chroma_synced, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_path, file_name, extension, file_size, modified_time, file_hash,
             status, int(bool(ocr_used)), now_str(), chroma_synced, chunk_count),
        )
        file_id = cur.lastrowid
    conn.commit()
    return file_id


def _ensure_risk_explanation_column(conn) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(analysis_results)")
    cols = [row[1] for row in cur.fetchall()]
    if "risk_explanation" not in cols:
        cur.execute("ALTER TABLE analysis_results ADD COLUMN risk_explanation TEXT")
        conn.commit()


def replace_analysis_result(conn, file_id: int, result: dict) -> None:
    _ensure_risk_explanation_column(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM analysis_results WHERE file_id = ?", (file_id,))
    cur.execute(
        """
        INSERT INTO analysis_results
        (file_id, document_type, summary, keywords_json, risk_score, risk_label,
         risk_categories_json, flagged_phrases_json, management_takeaway, word_count,
         char_count, mode, content_text, risk_explanation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            result.get("document_type"),
            result.get("summary"),
            json.dumps(result.get("keywords", []), ensure_ascii=False),
            int(result.get("risk_score", 0)),
            result.get("risk_label"),
            json.dumps(result.get("risk_categories", []), ensure_ascii=False),
            json.dumps(result.get("flagged_phrases", []), ensure_ascii=False),
            result.get("management_takeaway"),
            int(result.get("word_count", 0)),
            int(result.get("char_count", 0)),
            result.get("mode"),
            result.get("content"),
            result.get("risk_explanation"),
        ),
    )
    conn.commit()


def _sync_to_chroma(result: dict, file_path: str, chroma_dir: str) -> int:
    """Embed the document into ChromaDB. Returns chunk count (0 on failure)."""
    if not _CHROMA_AVAILABLE:
        return 0
    content = result.get("content", "")
    if not content or not content.strip():
        return 0
    try:
        file_name = result.get("filename") or result.get("file_name") or file_path.split("/")[-1]
        chunks = chunk_text(content, file_path=file_path, file_name=file_name)
        delete_by_file_path(file_path, persist_dir=chroma_dir)
        upsert_document(chunks, persist_dir=chroma_dir)
        return len(chunks)
    except Exception:
        return 0


def should_skip(conn, file_path: str, modified_time: float, file_hash: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT modified_time, file_hash, status FROM files WHERE file_path = ?", (file_path,))
    row = cur.fetchone()
    if not row:
        return False
    old_modified, old_hash, old_status = row
    return (old_modified == modified_time) and (old_hash == file_hash) and (old_status == "processed")


def process_folder_to_db(
    folder_path: str,
    db_path: str,
    mode: str = "Premium",
    recursive: bool = True,
    progress_callback: ProgressCallback = None,
) -> int:
    init_database(db_path)
    conn = get_connection(db_path)
    discovered = scan_folder(folder_path, recursive=recursive)
    run_id = create_run(conn, "folder", folder_path, len(discovered))
    ocr_config = load_ocr_config(db_path)
    chroma_dir = _load_chroma_dir(db_path)

    processed = skipped = failed = 0

    for idx, meta in enumerate(discovered, start=1):
        file_path = meta["file_path"]
        try:
            file_hash = compute_file_hash(file_path)
            if should_skip(conn, file_path, meta["modified_time"], file_hash):
                skipped += 1
                if progress_callback:
                    progress_callback(idx, len(discovered), f"Skipped unchanged: {meta['file_name']}")
                continue

            result = process_file_path(file_path, mode=mode, ocr_config=ocr_config)
            chunk_count = _sync_to_chroma(result, file_path, chroma_dir)
            chroma_synced = 1 if chunk_count > 0 else 0

            file_id = upsert_file_record(
                conn,
                file_path=file_path,
                file_name=meta["file_name"],
                extension=meta["extension"],
                file_size=meta["file_size"],
                modified_time=meta["modified_time"],
                file_hash=file_hash,
                status="processed",
                ocr_used=result.get("ocr_used", False),
                chroma_synced=chroma_synced,
                chunk_count=chunk_count,
            )
            replace_analysis_result(conn, file_id, result)
            processed += 1
            if progress_callback:
                progress_callback(idx, len(discovered), f"Processed: {meta['file_name']}")
        except Exception as exc:
            failed += 1
            log_error(conn, file_path, type(exc).__name__, str(exc))
            upsert_file_record(
                conn,
                file_path=file_path,
                file_name=meta["file_name"],
                extension=meta["extension"],
                file_size=meta["file_size"],
                modified_time=meta["modified_time"],
                file_hash="",
                status="failed",
                ocr_used=False,
            )
            if progress_callback:
                progress_callback(idx, len(discovered), f"Failed: {meta['file_name']}")

    finalize_run(conn, run_id, processed, skipped, failed, status="completed")
    conn.close()
    return run_id


def process_uploaded_files_to_db(
    uploaded_files,
    db_path: str,
    mode: str = "Premium",
    progress_callback: ProgressCallback = None,
) -> int:
    init_database(db_path)
    conn = get_connection(db_path)
    total = len(uploaded_files)
    run_id = create_run(conn, "upload", f"{total} uploaded files", total)
    ocr_config = load_ocr_config(db_path)
    chroma_dir = _load_chroma_dir(db_path)

    processed = skipped = failed = 0

    for idx, uploaded_file in enumerate(uploaded_files, start=1):
        pseudo_path = f"uploaded://{uploaded_file.name}"
        try:
            result = process_uploaded_file(uploaded_file, mode=mode, ocr_config=ocr_config)
            chunk_count = _sync_to_chroma(result, pseudo_path, chroma_dir)
            chroma_synced = 1 if chunk_count > 0 else 0

            file_id = upsert_file_record(
                conn,
                file_path=pseudo_path,
                file_name=uploaded_file.name,
                extension=result.get("filetype", ""),
                file_size=len(uploaded_file.getvalue()),
                modified_time=0.0,
                file_hash="uploaded-session",
                status="processed",
                ocr_used=result.get("ocr_used", False),
                chroma_synced=chroma_synced,
                chunk_count=chunk_count,
            )
            replace_analysis_result(conn, file_id, result)
            processed += 1
            if progress_callback:
                progress_callback(idx, total, f"Processed upload: {uploaded_file.name}")
        except Exception as exc:
            failed += 1
            log_error(conn, pseudo_path, type(exc).__name__, str(exc))
            if progress_callback:
                progress_callback(idx, total, f"Failed upload: {uploaded_file.name}")

    finalize_run(conn, run_id, processed, skipped, failed, status="completed")
    conn.close()
    return run_id


def get_run_stats(db_path: str, run_id: int):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT total_files, processed_files, skipped_files, failed_files, status
        FROM processing_runs WHERE id = ?
        """,
        (run_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "total_files": row[0],
        "processed_files": row[1],
        "skipped_files": row[2],
        "failed_files": row[3],
        "status": row[4],
    }


def sync_missing_to_chroma(db_path: str, progress_callback: ProgressCallback = None) -> int:
    """Embed all processed files that have not yet been synced to ChromaDB.

    Returns the number of files successfully synced.
    """
    if not _CHROMA_AVAILABLE:
        return 0

    chroma_dir = _load_chroma_dir(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, file_path, file_name FROM files WHERE chroma_synced = 0 AND status = 'processed'"
    )
    pending = cur.fetchall()
    conn.close()

    synced = 0
    total = len(pending)

    for idx, row in enumerate(pending, start=1):
        file_id, file_path, file_name = row[0], row[1], row[2]
        try:
            # Load content from analysis_results
            conn2 = get_connection(db_path)
            cur2 = conn2.cursor()
            cur2.execute("SELECT content_text FROM analysis_results WHERE file_id = ?", (file_id,))
            ar = cur2.fetchone()
            conn2.close()

            content = ar[0] if ar and ar[0] else ""
            if not content.strip():
                continue

            chunks = chunk_text(content, file_path=file_path, file_name=file_name)
            delete_by_file_path(file_path, persist_dir=chroma_dir)
            upsert_document(chunks, persist_dir=chroma_dir)
            chunk_count = len(chunks)

            conn3 = get_connection(db_path)
            cur3 = conn3.cursor()
            cur3.execute(
                "UPDATE files SET chroma_synced = 1, chunk_count = ? WHERE id = ?",
                (chunk_count, file_id),
            )
            conn3.commit()
            conn3.close()

            synced += 1
            if progress_callback:
                progress_callback(idx, total, f"Synced: {file_name}")
        except Exception:
            if progress_callback:
                progress_callback(idx, total, f"Failed to sync: {file_name}")

    return synced


def create_schedule(db_path: str, schedule_name: str, folder_path: str, frequency: str, recursive: bool = True, notes: str = "") -> None:
    conn = get_connection(db_path)
    cur = conn.cursor()
    next_run = datetime.now()
    cur.execute(
        """
        INSERT INTO scan_schedules (schedule_name, folder_path, recursive, enabled, frequency, next_run_at, notes)
        VALUES (?, ?, ?, 1, ?, ?, ?)
        """,
        (schedule_name, folder_path, int(bool(recursive)), frequency, next_run.strftime("%Y-%m-%d %H:%M:%S"), notes),
    )
    conn.commit()
    conn.close()


def list_schedules(db_path: str):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, schedule_name, folder_path, recursive, enabled, frequency, next_run_at, last_run_at, notes FROM scan_schedules ORDER BY id DESC"
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def update_schedule_status(db_path: str, schedule_id: int, enabled: bool) -> None:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE scan_schedules SET enabled = ? WHERE id = ?", (int(bool(enabled)), schedule_id))
    conn.commit()
    conn.close()


def _next_time_from_frequency(freq: str) -> datetime:
    now = datetime.now()
    mapping = {
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
    }
    return now + mapping.get(freq.lower(), timedelta(days=1))


def run_due_schedules(db_path: str, progress_callback: ProgressCallback = None) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, folder_path, recursive, frequency FROM scan_schedules WHERE enabled = 1 AND next_run_at <= ?",
        (now_str(),),
    )
    due = [dict(row) for row in cur.fetchall()]
    conn.close()
    ran = 0
    for idx, sched in enumerate(due, start=1):
        if progress_callback:
            progress_callback(idx, len(due), f"Running schedule {sched['id']}: {sched['folder_path']}")
        process_folder_to_db(
            folder_path=sched["folder_path"],
            db_path=db_path,
            mode="Premium",
            recursive=bool(sched["recursive"]),
        )
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute(
            "UPDATE scan_schedules SET last_run_at = ?, next_run_at = ? WHERE id = ?",
            (now_str(), _next_time_from_frequency(sched["frequency"]).strftime("%Y-%m-%d %H:%M:%S"), sched["id"]),
        )
        conn.commit()
        conn.close()
        ran += 1
    return ran
