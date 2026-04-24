# tests/test_llm_enricher.py
from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from unittest.mock import MagicMock

from src.llm_enricher import _parse_response, enrich_with_llm

_VALID_RAW = (
    "SUMMARY: This is a test document.\n"
    "TYPE: Contract\n"
    "RISK: There is moderate liability risk.\n"
    "TAKEAWAY: Legal review recommended."
)


def test_parse_response_returns_all_four_fields():
    result = _parse_response(_VALID_RAW)
    assert result is not None
    assert result["summary"] == "This is a test document."
    assert result["document_type"] == "Contract"
    assert result["risk_explanation"] == "There is moderate liability risk."
    assert result["management_takeaway"] == "Legal review recommended."


def test_parse_response_missing_field_returns_none():
    raw = "SUMMARY: Summary only.\nTYPE: Contract\nRISK: Some risk."
    assert _parse_response(raw) is None


def test_parse_response_empty_returns_none():
    assert _parse_response("") is None


def test_parse_response_extra_lines_ignored():
    raw = "Preamble text\n" + _VALID_RAW + "\nTrailing text"
    result = _parse_response(raw)
    assert result is not None
    assert result["document_type"] == "Contract"


def _make_llm(raw_content: str):
    mock_response = MagicMock()
    mock_response.content = raw_content
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


def test_enrich_with_llm_success():
    llm = _make_llm(_VALID_RAW)
    result = enrich_with_llm("some document content", "Medium", llm)
    assert result is not None
    assert result["document_type"] == "Contract"
    assert result["summary"] == "This is a test document."


def test_enrich_with_llm_malformed_response_returns_none():
    llm = _make_llm("SUMMARY: Only one field.")
    result = enrich_with_llm("content", "Low", llm)
    assert result is None


def test_enrich_with_llm_exception_returns_none():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("Ollama timeout")
    result = enrich_with_llm("content", "High", mock_llm)
    assert result is None


def test_enrich_with_llm_truncates_long_content():
    long_content = " ".join(["word"] * 2000)
    llm = _make_llm(_VALID_RAW)
    enrich_with_llm(long_content, "Low", llm)
    called_prompt = str(llm.invoke.call_args[0][0])
    # Truncated at exactly 1500 words — count of "word" in the prompt must be == 1500
    assert called_prompt.count("word") == 1500


def test_init_database_adds_llm_enriched_column():
    from src.database import init_database
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        init_database(db_path)
        with closing(sqlite3.connect(db_path)) as conn:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(files)").fetchall()]
        assert "llm_enriched" in cols


def test_process_file_bytes_enriches_when_llm_provided():
    from src.file_processor import process_file_bytes
    llm = _make_llm(_VALID_RAW)
    content = b"This is a sample contract document with some text content for testing."
    result = process_file_bytes("test.txt", content, llm=llm)
    assert result["llm_enriched"] == 1
    assert result["document_type"] == "Contract"
    assert result["summary"] == "This is a test document."
    assert isinstance(result["risk_score"], (int, float))
    assert result["risk_label"] in {"Low", "Medium", "High", "Critical"}
    assert isinstance(result["keywords"], list)


def test_process_file_bytes_skips_enrichment_when_llm_none():
    from src.file_processor import process_file_bytes
    content = b"This is a sample document."
    result = process_file_bytes("test.txt", content, llm=None)
    assert result["llm_enriched"] == 0
