# Heading-Aware Chunking & Tuned Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make section-specific queries on large heading-structured PDFs return correct answers by prepending the nearest section heading to every ChromaDB chunk and increasing chunk size and top_k.

**Architecture:** `chunker.py` gains a `_detect_sections()` function that splits extracted text into `(heading, body)` pairs via regex before calling `RecursiveCharacterTextSplitter`. Each chunk's text gets the heading prepended as `[Section: Natural Disaster]\n…` and the heading is stored in chunk metadata. `chunk_size` increases 500→1000, `chunk_overlap` 75→200, and `top_k` 4→8 across `vector_store.py`, `llm_interface.py`, and `app.py`. A re-ingestion notice is added in Operations → AI/RAG Settings.

**Tech Stack:** Python `re` (stdlib, no new deps), `langchain_text_splitters.RecursiveCharacterTextSplitter`, `pytest`, `streamlit`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `tests/test_chunker.py` | Unit tests for heading detection and heading-aware chunk_text |
| Modify | `src/rag/chunker.py` | Add `_detect_sections`, update `chunk_text`, tune chunk_size/overlap |
| Modify | `src/rag/vector_store.py` | Change `similarity_search` default `top_k` 4 → 8 |
| Modify | `src/rag/llm_interface.py` | Change `ask_with_rag` default `top_k` 4 → 8 |
| Modify | `app.py` lines 485, 828 | Change explicit `top_k=4` calls to `top_k=8` |
| Modify | `app.py` line 1038 | Add re-ingestion info banner in AI/RAG Settings tab |

---

## Task 1: Heading-aware `chunker.py` with tests (TDD)

**Files:**
- Create: `tests/test_chunker.py`
- Modify: `src/rag/chunker.py`

- [ ] **Step 1: Create `tests/test_chunker.py` with failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd "C:\Projects\INSIGHT_AI - Copy"
.venv\Scripts\activate
pytest tests/test_chunker.py -v
```

Expected: `ImportError: cannot import name '_detect_sections' from 'src.rag.chunker'`

- [ ] **Step 3: Replace the full contents of `src/rag/chunker.py`**

```python
from __future__ import annotations

import hashlib
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""],
)

_HEADING_RE = re.compile(
    r'^(?:'
    r'\d+(?:\.\d+)*\.?\s+\S.{0,69}'                       # numbered: "1. Foo", "2.3 Bar"
    r'|[A-Z][A-Z0-9 &/\-]{3,58}[A-Z0-9]'                  # ALL CAPS: "NATURAL DISASTER"
    r'|(?:[A-Z][a-z]{1,20})(?:\s[A-Z][a-z]{1,20}){1,6}'   # Title Case: "Natural Disaster"
    r')$'
)


def _file_id_prefix(file_path: str) -> str:
    return hashlib.sha256(file_path.encode()).hexdigest()[:16]


def _detect_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (heading, body) pairs using regex heading detection.

    A line is treated as a heading if it is ≤ 80 chars and matches _HEADING_RE.
    Content before the first heading is returned with heading="".
    """
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in text.splitlines(keepends=True):
        stripped = line.rstrip()
        if stripped and len(stripped) <= 80 and _HEADING_RE.match(stripped):
            if current_lines or current_heading:
                sections.append((current_heading, "".join(current_lines)))
            current_heading = stripped
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines or current_heading:
        sections.append((current_heading, "".join(current_lines)))

    return sections if sections else [("", text)]


def chunk_text(text: str, file_path: str, file_name: str) -> list[dict]:
    """Split *text* into overlapping chunks ready for embedding.

    Each chunk from a detected section is prefixed with
    "[Section: <heading>]\\n" so semantic search matches section-specific
    queries. Returns a list of dicts with keys: id, text, metadata.
    """
    if not text or not text.strip():
        return []

    prefix = _file_id_prefix(file_path)
    sections = _detect_sections(text)
    chunks: list[dict] = []
    chunk_idx = 0

    for heading, body in sections:
        if not body.strip():
            continue
        for raw in _SPLITTER.split_text(body):
            chunk_text_val = f"[Section: {heading}]\n{raw}" if heading else raw
            chunks.append({
                "id": f"{prefix}::chunk_{chunk_idx}",
                "text": chunk_text_val,
                "metadata": {
                    "file_path": file_path,
                    "file_name": file_name,
                    "chunk_index": chunk_idx,
                    "total_chunks": 0,
                    "section_heading": heading,
                },
            })
            chunk_idx += 1

    total = len(chunks)
    for c in chunks:
        c["metadata"]["total_chunks"] = total

    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_chunker.py -v
```

Expected: 11 tests PASSED.

- [ ] **Step 5: Run the full test suite to check for regressions**

```
pytest tests/ -v
```

Expected: all tests PASSED (the existing 13 LLM enricher tests should still pass).

- [ ] **Step 6: Commit**

```bash
git add tests/test_chunker.py src/rag/chunker.py
git commit -m "feat: heading-aware chunking with regex section detection and tuned chunk size"
```

---

## Task 2: Tune `top_k` defaults in `vector_store.py` and `llm_interface.py`

**Files:**
- Modify: `src/rag/vector_store.py` line 147
- Modify: `src/rag/llm_interface.py` line 53

- [ ] **Step 1: Update `similarity_search` default in `src/rag/vector_store.py`**

Change line 147 from:
```python
def similarity_search(query: str, top_k: int = 4, persist_dir: str = "data/chromadb") -> list[dict]:
```
to:
```python
def similarity_search(query: str, top_k: int = 8, persist_dir: str = "data/chromadb") -> list[dict]:
```

- [ ] **Step 2: Update `ask_with_rag` default in `src/rag/llm_interface.py`**

Change line 53 from:
```python
    top_k: int = 4,
```
to:
```python
    top_k: int = 8,
```

- [ ] **Step 3: Run full test suite**

```
pytest tests/ -v
```

Expected: all tests PASSED.

- [ ] **Step 4: Commit**

```bash
git add src/rag/vector_store.py src/rag/llm_interface.py
git commit -m "feat: increase default top_k from 4 to 8 for broader retrieval coverage"
```

---

## Task 3: Update explicit `top_k` calls and add re-ingestion banner in `app.py`

**Files:**
- Modify: `app.py` lines 485, 828, 1038

- [ ] **Step 1: Update `top_k=4` at line 485 (Home/chat path)**

Change:
```python
            result = ask_with_rag(
                question=question,
                llm=llm,
                persist_dir=_chroma_dir(),
                top_k=4,
                chat_history=st.session_state.chat_history,
            )
```
to:
```python
            result = ask_with_rag(
                question=question,
                llm=llm,
                persist_dir=_chroma_dir(),
                top_k=8,
                chat_history=st.session_state.chat_history,
            )
```

- [ ] **Step 2: Update `top_k=4` at line 828 (Ask Questions path)**

Change:
```python
                    result = ask_with_rag(q, llm=llm, persist_dir=_chroma_dir(), top_k=4)
```
to:
```python
                    result = ask_with_rag(q, llm=llm, persist_dir=_chroma_dir(), top_k=8)
```

- [ ] **Step 3: Add re-ingestion banner in Operations → AI/RAG Settings tab**

Find the `st.divider()` at line 1038 (inside `with tabs[4]:`, between the health metrics and `### Configuration`). Add the banner immediately after it:

Change:
```python
        st.divider()
        st.markdown("### Configuration")
```
to:
```python
        st.divider()
        st.info(
            "**Chunking updated:** Documents indexed before this update use smaller 500-character chunks "
            "without section heading prefixes. Re-ingest your files via the Ingestion Hub to enable "
            "heading-aware retrieval and improved Q&A accuracy on large documents."
        )
        st.markdown("### Configuration")
```

- [ ] **Step 4: Run full test suite**

```
pytest tests/ -v
```

Expected: all tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: raise top_k to 8 in app.py and add re-ingestion notice in AI/RAG Settings"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|---|---|
| Heading detection: numbered, all-caps, title-case | Task 1 `_HEADING_RE` |
| Pre-segment into (heading, body) pairs | Task 1 `_detect_sections` |
| Prepend `[Section: heading]` to each chunk text | Task 1 `chunk_text` |
| Store `section_heading` in chunk metadata | Task 1 `chunk_text` |
| Fallback: no headings → chunks without prefix | Task 1 `_detect_sections` returns `[("", text)]` |
| `chunk_size` 500 → 1000 | Task 1 `_SPLITTER` |
| `chunk_overlap` 75 → 200 | Task 1 `_SPLITTER` |
| `top_k` 4 → 8 in `vector_store.py` | Task 2 |
| `top_k` 4 → 8 in `llm_interface.py` | Task 2 |
| `top_k` 4 → 8 in `app.py` (both call sites) | Task 3 |
| Re-ingestion notice in Operations → AI/RAG Settings | Task 3 |
| No new Python dependencies | All tasks (uses stdlib `re` only) |

**Placeholder scan:** None found — all steps contain complete code.

**Type consistency:** `_detect_sections` returns `list[tuple[str, str]]` — consumed in `chunk_text` as `for heading, body in sections` — consistent. `chunk_text` return schema (`id`, `text`, `metadata` with `file_path`, `file_name`, `chunk_index`, `total_chunks`, `section_heading`) — `section_heading` is a new key, all existing callers only read the other four keys so no breakage.
