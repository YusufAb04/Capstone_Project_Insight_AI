from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Optional


DEFAULT_OCR_SETTINGS = {
    "ocr_enabled": "1",
    "ocr_page_limit": "30",
    "ocr_dpi": "220",
    "ocr_min_words_threshold": "30",
}

DEFAULT_RAG_SETTINGS = {
    "chroma_persist_dir": "data/chromadb",
    "ollama_model": "llama3.2:3b",
    "ollama_base_url": "http://localhost:11434",
}


def get_connection(db_path: str) -> sqlite3.Connection:
    db_file = Path(db_path)
    if db_file.parent.as_posix() not in {"", "."}:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cur, table: str, column: str, ddl: str) -> None:
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_database(db_path: str) -> None:
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT NOT NULL,
            extension TEXT,
            file_size INTEGER,
            modified_time REAL,
            file_hash TEXT,
            status TEXT DEFAULT 'pending',
            ocr_used INTEGER DEFAULT 0,
            last_processed_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            document_type TEXT,
            summary TEXT,
            keywords_json TEXT,
            risk_score INTEGER,
            risk_label TEXT,
            risk_categories_json TEXT,
            flagged_phrases_json TEXT,
            management_takeaway TEXT,
            word_count INTEGER,
            char_count INTEGER,
            mode TEXT,
            content_text TEXT,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS processing_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            finished_at TEXT,
            source_type TEXT,
            source_value TEXT,
            total_files INTEGER DEFAULT 0,
            processed_files INTEGER DEFAULT 0,
            skipped_files INTEGER DEFAULT 0,
            failed_files INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            error_type TEXT,
            error_message TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            action TEXT,
            target TEXT,
            details TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_name TEXT NOT NULL,
            folder_path TEXT NOT NULL,
            recursive INTEGER DEFAULT 1,
            enabled INTEGER DEFAULT 1,
            frequency TEXT NOT NULL,
            next_run_at TEXT,
            last_run_at TEXT,
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            completed_at TEXT,
            dataset_name TEXT,
            total_rows INTEGER DEFAULT 0,
            matched_rows INTEGER DEFAULT 0,
            risk_accuracy REAL DEFAULT 0,
            doc_type_accuracy REAL DEFAULT 0,
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            validation_run_id INTEGER NOT NULL,
            file_name TEXT,
            expected_risk_label TEXT,
            predicted_risk_label TEXT,
            expected_document_type TEXT,
            predicted_document_type TEXT,
            matched INTEGER DEFAULT 0,
            FOREIGN KEY(validation_run_id) REFERENCES validation_runs(id) ON DELETE CASCADE
        )
        """
    )

    # Additive migrations — safe to run on existing databases
    _ensure_column(cur, "analysis_results", "content_text", "content_text TEXT")
    _ensure_column(cur, "analysis_results", "risk_explanation", "risk_explanation TEXT")

    # RAG sync tracking columns
    _ensure_column(cur, "files", "chroma_synced", "chroma_synced INTEGER DEFAULT 0")
    _ensure_column(cur, "files", "chunk_count", "chunk_count INTEGER DEFAULT 0")

    # LLM enrichment flag
    _ensure_column(cur, "files", "llm_enriched", "llm_enriched INTEGER DEFAULT 0")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_chroma ON files(chroma_synced, status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_analysis_file_id ON analysis_results(file_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_schedule_enabled_next ON scan_schedules(enabled, next_run_at)")

    for key, value in {**DEFAULT_OCR_SETTINGS, **DEFAULT_RAG_SETTINGS}.items():
        cur.execute(
            "INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    conn.commit()
    conn.close()


def get_setting(db_path: str, key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(db_path: str, key: str, value: str) -> None:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """,
        (key, value),
    )
    conn.commit()
    conn.close()


def get_exclusion_keywords(db_path: str) -> list[str]:
    raw = get_setting(db_path, "exclusion_keywords", "[]")
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return []


def set_exclusion_keywords(db_path: str, keywords: list[str]) -> None:
    set_setting(db_path, "exclusion_keywords", json.dumps(keywords))


def backup_database(db_path: str, backup_path: str) -> str:
    src = Path(db_path)
    dst = Path(backup_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst)


def restore_database(db_path: str, restore_from_path: str) -> None:
    src = Path(restore_from_path)
    dst = Path(db_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
