"""Tests for verify_chunk_counts and reingest_single_file in batch_processor."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch


_CREATE_FILES_TABLE = """
    CREATE TABLE files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        file_name TEXT,
        extension TEXT,
        file_size INTEGER DEFAULT 0,
        modified_time REAL DEFAULT 0,
        file_hash TEXT,
        status TEXT,
        ocr_used INTEGER DEFAULT 0,
        last_processed_at TEXT,
        chroma_synced INTEGER DEFAULT 0,
        chunk_count INTEGER DEFAULT 0,
        llm_enriched INTEGER DEFAULT 0
    )
"""

_INSERT_FILE = """
    INSERT INTO files (file_path, file_name, extension, file_size,
        modified_time, file_hash, status, ocr_used, last_processed_at,
        chroma_synced, chunk_count, llm_enriched)
    VALUES (:file_path, :file_name, :extension, :file_size,
        :modified_time, :file_hash, :status, :ocr_used, :last_processed_at,
        :chroma_synced, :chunk_count, :llm_enriched)
"""


def _make_temp_db_with_files(rows: list[dict]) -> str:
    """Create a real temp-file SQLite DB and return its path. Caller must os.unlink it."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    conn = sqlite3.connect(tmp_path)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_FILES_TABLE)
    for row in rows:
        conn.execute(_INSERT_FILE, {
            "file_path": row.get("file_path", "/tmp/test.txt"),
            "file_name": row.get("file_name", "test.txt"),
            "extension": row.get("extension", "txt"),
            "file_size": row.get("file_size", 100),
            "modified_time": row.get("modified_time", 0.0),
            "file_hash": row.get("file_hash", "abc123"),
            "status": row.get("status", "processed"),
            "ocr_used": row.get("ocr_used", 0),
            "last_processed_at": row.get("last_processed_at", "2024-01-01 00:00:00"),
            "chroma_synced": row.get("chroma_synced", 1),
            "chunk_count": row.get("chunk_count", 5),
            "llm_enriched": row.get("llm_enriched", 0),
        })
    conn.commit()
    conn.close()
    return tmp_path


def _make_in_memory_db_with_files(rows: list[dict]) -> sqlite3.Connection:
    """Create an in-memory SQLite DB. Used for tests that need to inspect the
    connection object while it's still open (reingest tests)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_FILES_TABLE)
    for row in rows:
        conn.execute(_INSERT_FILE, {
            "file_path": row.get("file_path", "/tmp/test.txt"),
            "file_name": row.get("file_name", "test.txt"),
            "extension": row.get("extension", "txt"),
            "file_size": row.get("file_size", 100),
            "modified_time": row.get("modified_time", 0.0),
            "file_hash": row.get("file_hash", "abc123"),
            "status": row.get("status", "processed"),
            "ocr_used": row.get("ocr_used", 0),
            "last_processed_at": row.get("last_processed_at", "2024-01-01 00:00:00"),
            "chroma_synced": row.get("chroma_synced", 1),
            "chunk_count": row.get("chunk_count", 5),
            "llm_enriched": row.get("llm_enriched", 0),
        })
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Test 1: verify_chunk_counts detects a broken file (chroma returns 0 ids)
# ---------------------------------------------------------------------------
class TestVerifyFindsBrokenFile(unittest.TestCase):
    def test_verify_finds_broken_file(self):
        broken_path = "/data/broken.txt"
        db_path = _make_temp_db_with_files([
            {"file_path": broken_path, "chroma_synced": 1, "chunk_count": 5}
        ])
        self.addCleanup(os.unlink, db_path)

        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": []}

        with patch("src.batch_processor.get_collection", return_value=mock_collection):
            from src.batch_processor import verify_chunk_counts
            results = verify_chunk_counts(db_path, "fake/chroma/dir")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["file_path"], broken_path)
        self.assertEqual(results[0]["db_chunk_count"], 5)
        self.assertEqual(results[0]["chroma_chunk_count"], 0)
        self.assertEqual(results[0]["status"], "broken")

        # verify_chunk_counts closed its connection; open a new one to inspect state
        check_conn = sqlite3.connect(db_path)
        check_conn.row_factory = sqlite3.Row
        row = check_conn.execute(
            "SELECT chroma_synced, chunk_count FROM files WHERE file_path = ?",
            (broken_path,),
        ).fetchone()
        check_conn.close()
        self.assertEqual(row["chroma_synced"], 0)
        self.assertEqual(row["chunk_count"], 0)


# ---------------------------------------------------------------------------
# Test 2: verify_chunk_counts returns "ok" for a healthy file
# ---------------------------------------------------------------------------
class TestVerifyOkFile(unittest.TestCase):
    def test_verify_ok_file(self):
        ok_path = "/data/ok.txt"
        db_path = _make_temp_db_with_files([
            {"file_path": ok_path, "chroma_synced": 1, "chunk_count": 3}
        ])
        self.addCleanup(os.unlink, db_path)

        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": ["id1", "id2", "id3"]}

        with patch("src.batch_processor.get_collection", return_value=mock_collection):
            from src.batch_processor import verify_chunk_counts
            results = verify_chunk_counts(db_path, "fake/chroma/dir")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["file_path"], ok_path)
        self.assertEqual(results[0]["db_chunk_count"], 3)
        self.assertEqual(results[0]["chroma_chunk_count"], 3)
        self.assertEqual(results[0]["status"], "ok")

        check_conn = sqlite3.connect(db_path)
        check_conn.row_factory = sqlite3.Row
        row = check_conn.execute(
            "SELECT chroma_synced, chunk_count FROM files WHERE file_path = ?",
            (ok_path,),
        ).fetchone()
        check_conn.close()
        self.assertEqual(row["chroma_synced"], 1)
        self.assertEqual(row["chunk_count"], 3)


# ---------------------------------------------------------------------------
# Test 3: verify_chunk_counts skips files where chroma_synced = 0
# ---------------------------------------------------------------------------
class TestVerifySkipsUnsyncedFiles(unittest.TestCase):
    def test_verify_skips_unsynced_files(self):
        unsynced_path = "/data/unsynced.txt"
        db_path = _make_temp_db_with_files([
            {"file_path": unsynced_path, "chroma_synced": 0, "chunk_count": 0}
        ])
        self.addCleanup(os.unlink, db_path)

        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": []}

        with patch("src.batch_processor.get_collection", return_value=mock_collection):
            from src.batch_processor import verify_chunk_counts
            results = verify_chunk_counts(db_path, "fake/chroma/dir")

        paths_in_results = [r["file_path"] for r in results]
        self.assertNotIn(unsynced_path, paths_in_results)
        self.assertEqual(len(results), 0)


# ---------------------------------------------------------------------------
# Test 4: reingest_single_file returns success with correct chunk count
# ---------------------------------------------------------------------------
class TestReingestSingleFileSuccess(unittest.TestCase):
    def test_reingest_single_file_success(self):
        file_path = "/data/report.txt"
        in_mem_conn = _make_in_memory_db_with_files([
            {"file_path": file_path, "chroma_synced": 0, "chunk_count": 0}
        ])

        fake_chunks = [
            {"id": "chunk_0", "text": "chunk1", "metadata": {"file_path": file_path}},
            {"id": "chunk_1", "text": "chunk2", "metadata": {"file_path": file_path}},
        ]

        with (
            patch("src.batch_processor.get_connection", return_value=in_mem_conn),
            patch("src.batch_processor._extract_text_for_reingest", return_value="Hello world"),
            patch("src.batch_processor.chunk_text", return_value=fake_chunks),
            patch("src.batch_processor.get_collection"),
            patch("src.batch_processor.upsert_document") as mock_upsert,
        ):
            from src.batch_processor import reingest_single_file
            result = reingest_single_file(":memory:", file_path, "fake/chroma/dir")

        self.assertTrue(result["success"])
        self.assertEqual(result["chunk_count"], 2)
        self.assertEqual(result["error"], "")
        mock_upsert.assert_called_once_with(fake_chunks, persist_dir="fake/chroma/dir")


# ---------------------------------------------------------------------------
# Test 5: reingest_single_file returns failure when no text extracted
# ---------------------------------------------------------------------------
class TestReingestSingleFileNoText(unittest.TestCase):
    def test_reingest_single_file_no_text(self):
        file_path = "/data/empty.txt"

        with (
            patch("src.batch_processor._extract_text_for_reingest", return_value=""),
        ):
            from src.batch_processor import reingest_single_file
            result = reingest_single_file(":memory:", file_path, "fake/chroma/dir")

        self.assertFalse(result["success"])
        self.assertEqual(result["chunk_count"], 0)
        self.assertEqual(result["error"], "No text extracted")


if __name__ == "__main__":
    unittest.main()
