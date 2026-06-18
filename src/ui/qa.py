from __future__ import annotations

from collections import Counter
from datetime import datetime

import streamlit as st

from src.ui.deps import TfidfVectorizer, ask_with_rag, cosine_similarity
from src.ui.helpers import load_records
from src.ui.rag_helpers import _check_rag, _chroma_dir, _get_llm

_HOME_SUGGESTIONS = [
    "What are the main risks management should focus on right now?",
    "Which files are the highest risk and why?",
    "Are there repeated compliance or security issues across the dataset?",
    "What opportunities for improvement appear across these documents?",
]


def _source_chips_html(sources: list[str]) -> str:
    if not sources:
        return ""
    chips = "".join(f'<span class="src-chip">{fname}</span>' for fname in sources)
    return (
        '<div style="margin-top:10px;padding-left:2px;">'
        '<div class="src-chips-label">SOURCES</div>'
        f'{chips}</div>'
    )


# ---------------------------------------------------------------------------
# Q&A: TF-IDF fallback path
# ---------------------------------------------------------------------------

def _score_question_against_record(question: str, record: dict) -> tuple[float, str]:
    text = " ".join([
        record.get("summary") or "",
        record.get("management_takeaway") or "",
        " ".join(record.get("keywords") or []),
        " ".join(record.get("flagged_phrases") or []),
        record.get("content_text") or "",
    ])
    if not text.strip():
        return 0.0, ""
    if TfidfVectorizer is not None and cosine_similarity is not None:
        try:
            vec = TfidfVectorizer(stop_words="english")
            matrix = vec.fit_transform([question, text])
            score = float(cosine_similarity(matrix[0:1], matrix[1:2]).flatten()[0])
        except Exception:
            score = 0.0
    else:
        q_terms = set(question.lower().split())
        t_terms = text.lower().split()
        score = sum(t_terms.count(term) for term in q_terms)
    excerpt = next(
        (sent for sent in text.split(". ") if any(tok in sent.lower() for tok in question.lower().split()[:4])),
        text[:300],
    )
    return score, excerpt.strip()


def _run_question_tfidf(question: str) -> tuple[str, list[str]]:
    records = load_records()
    scored = []
    for rec in records:
        score, excerpt = _score_question_against_record(question, rec)
        if score > 0:
            scored.append((score, excerpt, rec))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:4]

    if not top:
        return "No strong evidence matched. Ingest some documents first via **Ingestion Hub**.", []

    top_labels = Counter((rec.get("risk_label") or "Unknown") for _, _, rec in top)
    top_types = Counter((rec.get("document_type") or "Unknown") for _, _, rec in top)
    risk_categories = Counter(cat for _, _, rec in top for cat in (rec.get("risk_categories") or []))
    flagged = Counter(flag for _, _, rec in top for flag in (rec.get("flagged_phrases") or []))
    conf = "High" if top[0][0] > 0.15 or len(top) >= 3 else "Moderate"

    answer = (
        f"Based on indexed evidence, the strongest signals are in "
        f"**{', '.join(rec.get('file_name') for _, _, rec in top[:3])}**. "
        f"Confidence: **{conf}**. "
        f"Risk levels: {', '.join(f'{k} ({v})' for k, v in top_labels.items())}. "
        f"Dominant categories: {', '.join(k for k, _ in risk_categories.most_common(4)) or 'none detected'}. "
        f"Key signals: {', '.join(k for k, _ in flagged.most_common(6)) or 'none'}. "
        f"Document types: {', '.join(f'{k} ({v})' for k, v in top_types.items())}."
    )
    sources = [rec.get("file_name", "") for _, _, rec in top if rec.get("file_name")]
    return answer, sources


# ---------------------------------------------------------------------------
# Q&A: RAG path
# ---------------------------------------------------------------------------

def _run_question_rag(question: str, prior_history: list[dict] | None = None) -> dict | None:
    llm = _get_llm()
    if llm is None:
        return None

    try:
        result = ask_with_rag(
            question=question,
            llm=llm,
            persist_dir=_chroma_dir(),
            top_k=8,
            chat_history=prior_history,
        )
    except Exception as exc:
        st.warning(f"AI answer failed ({exc}). Falling back to keyword search.")
        return None

    return result


def _run_question(question: str) -> None:
    chroma_ok, ollama_ok = _check_rag()
    now = datetime.now().strftime("%H:%M")

    # Snapshot history before appending the current message so the RAG call
    # only sees prior turns, not the question it's about to answer.
    prior_history = list(st.session_state.chat_history)
    st.session_state.chat_history.append({"role": "user", "content": question, "sources": [], "time": now})

    answer: str | None = None
    sources: list[str] = []
    error_type: str | None = None

    if chroma_ok and ollama_ok:
        with st.spinner("Thinking…"):
            rag_result = _run_question_rag(question, prior_history=prior_history)
        if rag_result:
            answer = rag_result.get("answer")
            sources = rag_result.get("sources") or []
            error_type = rag_result.get("error_type")

    if (answer is None and error_type is None) or error_type == "ollama_timeout":
        tfidf_answer, tfidf_sources = _run_question_tfidf(question)
        if error_type == "ollama_timeout":
            answer = "⚠️ *Ollama timed out — using keyword search.*\n\n" + tfidf_answer
        elif chroma_ok and not ollama_ok:
            answer = "⚠️ *Ollama offline — using keyword search. Start Ollama for AI-powered answers.*\n\n" + tfidf_answer
        else:
            answer = tfidf_answer
        sources = tfidf_sources
        error_type = None

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer if error_type is None else "",
        "sources": sources,
        "time": now,
        "error_type": error_type,
    })
