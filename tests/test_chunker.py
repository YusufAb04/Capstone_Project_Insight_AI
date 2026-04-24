# tests/test_chunker.py
from src.rag.chunker import _detect_sections, chunk_text

_NUMBERED_DOC = (
    "Preamble before any heading.\n\n"
    "1. Introduction\n"
    "This is the introduction body text.\n\n"
    "2. Natural Disaster\n"
    "Flooding and earthquakes pose a significant risk.\n"
    "Heavy rainfall has historically caused disruption.\n\n"
    "2.1 Flood Risk\n"
    "Flood risk is assessed annually.\n"
)

_ALLCAPS_DOC = (
    "EXECUTIVE SUMMARY\n"
    "This document outlines the key risks.\n\n"
    "NATURAL DISASTER\n"
    "Flooding poses a significant threat.\n"
)

_TITLECASE_DOC = (
    "Natural Disaster\n"
    "Flooding and earthquakes pose a significant risk.\n\n"
    "Risk Management Framework\n"
    "We manage risk through quarterly reviews.\n"
)

_PLAIN_DOC = "word " * 300


def test_detect_sections_numbered_headings():
    sections = _detect_sections(_NUMBERED_DOC)
    headings = [h for h, _ in sections]
    assert "1. Introduction" in headings
    assert "2. Natural Disaster" in headings
    assert "2.1 Flood Risk" in headings


def test_detect_sections_allcaps_headings():
    sections = _detect_sections(_ALLCAPS_DOC)
    headings = [h for h, _ in sections]
    assert "EXECUTIVE SUMMARY" in headings
    assert "NATURAL DISASTER" in headings


def test_detect_sections_titlecase_headings():
    sections = _detect_sections(_TITLECASE_DOC)
    headings = [h for h, _ in sections]
    assert "Natural Disaster" in headings
    assert "Risk Management Framework" in headings


def test_detect_sections_body_assigned_to_heading():
    sections = _detect_sections(_ALLCAPS_DOC)
    nd_body = next(body for h, body in sections if h == "NATURAL DISASTER")
    assert "Flooding" in nd_body


def test_detect_sections_no_headings_returns_single_section():
    sections = _detect_sections(_PLAIN_DOC)
    assert len(sections) == 1
    heading, body = sections[0]
    assert heading == ""
    assert "word" in body


def test_chunk_text_heading_prefix_in_chunk_text():
    chunks = chunk_text(_ALLCAPS_DOC, "risk.pdf", "risk.pdf")
    nd_chunks = [c for c in chunks if "NATURAL DISASTER" in c["text"]]
    assert nd_chunks, "Expected chunks with [Section: NATURAL DISASTER] prefix"
    assert nd_chunks[0]["text"].startswith("[Section: NATURAL DISASTER]")


def test_chunk_text_section_heading_in_metadata():
    chunks = chunk_text(_ALLCAPS_DOC, "risk.pdf", "risk.pdf")
    nd_chunks = [c for c in chunks if c["metadata"]["section_heading"] == "NATURAL DISASTER"]
    assert nd_chunks


def test_chunk_text_no_headings_no_prefix():
    chunks = chunk_text(_PLAIN_DOC, "plain.txt", "plain.txt")
    assert len(chunks) > 0
    assert all(not c["text"].startswith("[Section:") for c in chunks)


def test_chunk_text_total_chunks_consistent():
    chunks = chunk_text(_NUMBERED_DOC, "doc.pdf", "doc.pdf")
    total = len(chunks)
    assert total > 0
    assert all(c["metadata"]["total_chunks"] == total for c in chunks)


def test_chunk_text_chunk_indices_sequential():
    chunks = chunk_text(_NUMBERED_DOC, "doc.pdf", "doc.pdf")
    indices = [c["metadata"]["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks)))


def test_chunk_text_empty_returns_empty():
    assert chunk_text("", "empty.txt", "empty.txt") == []
    assert chunk_text("   ", "empty.txt", "empty.txt") == []
