# Heading-Aware Chunking & Tuned Retrieval — Design Spec

**Date:** 2026-04-25
**Status:** Approved

---

## Problem

Large PDFs with section headings (e.g. `enterprise-risk-assessment.pdf`) fail to return relevant answers for section-specific queries such as "summarise the Natural Disaster section." The failure is a **retrieval failure**, not a generation failure:

- `chunk_size=500` produces hundreds of tiny chunks from a 2 MB document.
- `top_k=4` means the LLM sees only 4 chunks (≈2 000 chars) out of potentially 400+.
- Section headings and their body content land in separate chunks with no link between them, so a query like "Natural Disaster" has low cosine similarity to chunks that say "Flooding and earthquakes pose a significant…" without the heading present.

---

## Goal

Make section-specific queries on large, heading-structured PDFs return correct, relevant answers by:

1. Prepending the nearest parent heading to every chunk so retrieval is structurally aware.
2. Increasing chunk size and overlap so each chunk carries more context.
3. Increasing `top_k` so more of the document is visible to the LLM.

---

## What Changes

### 1. Heading-aware chunking (`src/rag/chunker.py`)

**Heading detection:** Before splitting, the chunker scans extracted text line-by-line and classifies a line as a heading if it is ≤ 80 characters and matches any of:

| Pattern | Examples |
|---------|---------|
| Numbered sections | `1.`, `2.3`, `3.1.1 Natural Disaster` |
| All-caps lines | `NATURAL DISASTER`, `EXECUTIVE SUMMARY` |
| Short title-case lines (4–60 chars) | `Natural Disaster`, `Risk Management Framework` |

**Pre-segmentation:** The document is split into `(heading, body)` pairs before chunking. Each pair is chunked independently by `RecursiveCharacterTextSplitter`. Every chunk produced from a section gets the heading prepended to its text:

```
[Section: Natural Disaster]
Flooding and earthquakes pose a significant operational risk to the organisation…
```

The heading is also stored in the chunk's `metadata` dict under the key `section_heading` for future use (filtering, display).

**Fallback:** Lines with no detected heading are grouped under the previous heading. If no heading has been detected yet, chunks are produced without a prefix.

**No new dependencies** — heading detection uses the standard library `re` module only.

### 2. Tuned retrieval parameters

| Parameter | File | Before | After | Reason |
|-----------|------|--------|-------|--------|
| `chunk_size` | `chunker.py` | 500 | 1 000 | Full paragraphs instead of sentence fragments |
| `chunk_overlap` | `chunker.py` | 75 | 200 | Reduces boundary splits of key sentences |
| `top_k` default | `vector_store.py`, `llm_interface.py`, `app.py` | 4 | 8 | 8 × ~1 000 chars ≈ 2 000 tokens; fits within `num_ctx=4096` |

`num_ctx` on the LLM stays at 4 096 — 8 chunks × 1 000 chars ≈ 2 000 tokens of context, leaving ample room for the prompt template, question, and answer.

### 3. Re-ingestion notice (`app.py` — Operations → AI/RAG Settings)

A static informational banner is added to the AI/RAG Settings tab explaining that chunking parameters have been updated and existing documents should be re-processed via the Ingestion Hub to benefit from heading-aware chunks. The banner shows the current ChromaDB chunk count so users can judge scale.

No automatic destructive action is taken. Old chunks continue to work for general queries; they just don't carry the heading prefix boost.

---

## Architecture

```
PDF text (extracted by file_processor.py)
  └─▶ chunker.chunk_text()
        ├─▶ _detect_sections(text)       ← NEW: regex heading scan → [(heading, body), ...]
        │     └─▶ _HEADING_RE (compiled regex)
        ├─▶ For each (heading, body):
        │     └─▶ _SPLITTER.split_text(body)  ← existing RecursiveCharacterTextSplitter
        │           └─▶ Prepend "[Section: {heading}]\n" to each chunk
        │                 and add section_heading to metadata
        └─▶ Return flat list of chunk dicts (same schema as before)
```

The output schema of `chunk_text()` is unchanged — same `id`, `text`, `metadata` keys — so `vector_store.upsert_document()` and all callers require no changes beyond `top_k`.

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| No headings detected in document | Chunks produced without prefix — same as current behaviour |
| Heading regex matches a false positive (e.g. a table header) | Chunk gets an incorrect prefix; retrieval still improves for real headings; no crash |
| Heading is longer than 80 chars | Not detected as heading; falls under previous heading |
| Re-ingestion not performed after upgrade | Old chunks work normally; users see the Operations banner reminding them |

---

## Out of Scope

- BM25/hybrid search (Option C from brainstorming)
- Parent-child chunk retrieval
- Font-size-based heading detection (requires PyMuPDF)
- Automatic re-indexing of existing documents
- Per-file `top_k` tuning
- Changing `num_ctx` on the LLM
