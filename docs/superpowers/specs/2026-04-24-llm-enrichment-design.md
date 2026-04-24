# LLM Analysis Enrichment — Design Spec

**Date:** 2026-04-24
**Status:** Approved

---

## Goal

Upgrade the four explanatory text fields produced during document analysis — `summary`, `document_type`, `risk_explanation`, `management_takeaway` — from rule-based keyword outputs to LLM-generated plain-English text using the locally running Ollama instance (llama3.2:3b). Risk scores, risk labels, and keywords remain rule-based for speed and determinism.

---

## Context

INSIGHT_AI currently runs four rule-based analysis modules on every ingested document:

- **Classifier** — keyword-count across 8 hardcoded categories; misclassifies documents with overlapping vocabulary
- **Summarizer** — extracts top-3 sentences by word frequency; output reads as disconnected fragments
- **Risk engine** — matches keyword lists, sums weights, caps at 85; identical scores for "no liability" and "significant liability"
- **Keyword extractor** — frequency + business-priority boost; kept as-is (rule-based is fine here)

Ollama (llama3.2:3b) is already installed and running for the RAG Q&A feature. The machine has 16 GB RAM — llama3.2:3b (~2.1 GB) runs comfortably alongside the embedding model (~280 MB).

---

## What Changes

### Fields upgraded by LLM

| Field | Before | After |
|-------|--------|-------|
| `summary` | 3 extracted sentences (may be incoherent) | 2–3 sentence plain-English abstract |
| `document_type` | Keyword-count classification (context-blind) | LLM classification with context |
| `risk_explanation` | Template listing matched keyword categories | 1–2 sentences explaining *why* the document is risky |
| `management_takeaway` | Template-filled sentence | 1–2 sentence executive summary |

### Fields that stay rule-based

| Field | Reason |
|-------|--------|
| `risk_score` | Deterministic, consistent, offline-capable |
| `risk_label` | Derived from `risk_score` |
| `keywords` | Frequency-based extraction is fast and adequate |

---

## Architecture

### New module: `src/llm_enricher.py`

Single public function:

```python
def enrich_with_llm(content: str, risk_label: str, llm: ChatOllama) -> dict | None
```

- Truncates `content` to ~1 500 words to fit the 4 096-token context window
- Makes one LLM call with a delimiter-based prompt (more reliable than JSON with 3B models)
- Parses the four fields from the response
- Returns `{"summary": ..., "document_type": ..., "risk_explanation": ..., "management_takeaway": ...}` on success
- Returns `None` on any failure (parse error, Ollama timeout, exception)

### Prompt format

```
Analyse this document and respond in exactly this format — no extra text:
SUMMARY: <2-3 sentence plain-English summary>
TYPE: <one of: Invoice / Contract / Policy / Meeting Notes / HR Document / Financial Record / Report / Security Document / General Business File>
RISK: <1-2 sentences explaining the main risks, or "No significant risks identified." if low risk>
TAKEAWAY: <1-2 sentences for an executive>

Risk level assessed by rules: {risk_label}

Document (may be truncated):
{text}
```

Passing `risk_label` as a hint anchors the LLM's risk explanation to the score already computed, preventing contradictory outputs (e.g., LLM saying "low risk" when the score is Critical).

### Parsing

Response is split on newlines. Each field is extracted by prefix (`SUMMARY:`, `TYPE:`, `RISK:`, `TAKEAWAY:`). If any field is missing or the response is malformed, the function returns `None` and the caller falls back to rule-based outputs.

### Changes to `src/file_processor.py`

`process_file_bytes()` gains an optional `llm: ChatOllama | None = None` parameter. After the rule-based pass:

```python
if llm is not None:
    enriched = enrich_with_llm(analysis_text, result["risk_label"], llm)
    if enriched:
        result.update(enriched)
```

The rule-based fields not covered by `enriched` (score, label, keywords) are untouched.

### Changes to `src/batch_processor.py`

**During ingestion:** A single `ChatOllama` instance is created once before the processing loop (if Ollama is reachable). It is passed to each `process_file_bytes()` call. If Ollama is unreachable, `llm=None` is passed and all files fall back to rule-based outputs. After processing, `llm_enriched = 1` is written to the `files` row for successfully enriched files.

**Batch enrichment:** New function:

```python
def enrich_existing_with_llm(db_path: str, llm: ChatOllama, progress_callback=None) -> int
```

- Queries `files JOIN analysis_results` where `llm_enriched = 0` and `status = 'processed'`
- For each file: reads `content_text`, calls `enrich_with_llm`, updates `analysis_results` row, sets `files.llm_enriched = 1`
- Calls `progress_callback(done, total, filename)` if provided
- Returns count of successfully enriched files

### Database change

One new column added via the existing safe migration pattern in `database.py`:

```python
_ensure_column(cur, "files", "llm_enriched", "INTEGER DEFAULT 0")
```

### Changes to `app.py`

**Operations → AI/RAG Settings tab:**
- Add "Enrich existing files with AI" button below the health metrics
- Shows a progress bar while running (`enrich_existing_with_llm` with callback)
- Displays count of enriched files on completion

**File Explorer → Browse Files tab:**
- File name column shows `✨` prefix for files where `llm_enriched = 1`

**Ingestion Hub:**
- No UI change needed — the LLM step runs transparently within the existing per-file progress

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| Ollama offline at ingestion start | `llm=None` passed; all files use rule-based outputs; `llm_enriched` stays 0 |
| Ollama goes offline mid-batch | Per-file `enrich_with_llm` returns `None`; that file keeps rule-based output; batch continues |
| LLM response malformed | Parser returns `None`; rule-based outputs used; `llm_enriched` stays 0 |
| LLM response missing one field | Parser returns `None` for the whole call; no partial updates |
| Enrichment batch interrupted | Already-enriched files have `llm_enriched = 1`; re-running skips them |

---

## Constraints

- No new Python packages required — `langchain_ollama.ChatOllama` is already installed
- `llm_enricher.py` has no imports from `app.py` or Streamlit — it is a pure processing module
- Input text is always truncated before the LLM call; no document can exceed the context window
- The LLM model used for enrichment is the same model configured in RAG settings (`ollama_model` in `system_settings`) — no separate config needed

---

## Out of Scope

- Improving `risk_score` or `risk_label` with LLM (stays rule-based)
- Improving `keywords` with LLM (stays rule-based)
- Streaming LLM output to the UI during enrichment
- Changing the Ollama model specifically for enrichment
- Re-ingesting files from disk to re-extract text (enrichment uses stored `content_text`)
