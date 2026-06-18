from __future__ import annotations

import requests
import httpx

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from src.rag.vector_store import hybrid_search

_RAG_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a document analyst for an organisation's internal document library. "
        "Answer the user's question using ONLY the information in the context provided below. "
        "If the context contains relevant information, answer directly — do NOT open with any disclaimer or caveat. "
        "ONLY use the phrase 'The indexed documents do not contain enough information to answer this question.' "
        "if the context contains absolutely no relevant information about the topic. "
        "If the context is partially relevant, answer what you can and note what is missing. "
        "Always cite the source document name and section when referencing specific information.\n\n"
        "Context:\n{context}",
    ),
    ("human", "{question}"),
])


def check_ollama_status(base_url: str = "http://localhost:11434") -> bool:
    """Return True if the Ollama service is reachable."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def get_llm(model_name: str = "llama3.2:3b", base_url: str = "http://localhost:11434") -> ChatOllama:
    """Return a ChatOllama instance configured for low-RAM document QA."""
    return ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.1,
        num_ctx=4096,
    )


def _format_docs(chunks: list[dict]) -> str:
    parts = []
    for chunk in chunks:
        fname = chunk["metadata"].get("file_name", "unknown")
        parts.append(f"[Source: {fname}]\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)


# Cosine distance threshold above which a chunk is considered too dissimilar.
# ChromaDB with hnsw:space="cosine" returns distances in [0, 2]; 0 = identical,
# 2 = completely opposite. Finance/tabular data tends to produce higher distances
# even for relevant content — 1.5 blocks only near-zero matches.
_LOW_SIMILARITY_THRESHOLD = 1.5


def _run_chain(chain, prompt_input: dict) -> str:
    """Invoke *chain* and return the string result.

    Isolated here so tests can mock it cleanly and so timeout exceptions are
    caught in a single place.
    """
    return chain.invoke(prompt_input)


def ask_with_rag(
    question: str,
    llm: ChatOllama,
    persist_dir: str = "data/chromadb",
    top_k: int = 15,
    chat_history: list[dict] | None = None,
) -> dict:
    """Run a RAG query and return the answer with source references.

    Returns a dict with keys:
        answer       — LLM-generated answer string
        sources      — list of unique file names cited
        chunks_used  — number of chunks retrieved
        chunks       — raw chunk dicts (for UI display)
        error_type   — None | "no_chunks" | "low_similarity" | "ollama_timeout"
    """
    chunks = hybrid_search(question, top_k=top_k, persist_dir=persist_dir)

    if not chunks:
        return {
            "answer": "No searchable content found.",
            "sources": [],
            "chunks_used": 0,
            "chunks": [],
            "error_type": "no_chunks",
        }

    # Reject results where every chunk with a real vector distance is too far.
    # BM25-only chunks (distance=None) count as a signal that something keyword-relevant exists.
    vector_chunks = [c for c in chunks if c.get("distance") is not None]
    if vector_chunks and all(c["distance"] > _LOW_SIMILARITY_THRESHOLD for c in vector_chunks) and not any(c.get("distance") is None for c in chunks):
        return {
            "answer": "Found content but nothing closely matched your question.",
            "sources": [],
            "chunks_used": len(chunks),
            "chunks": chunks,
            "error_type": "low_similarity",
        }

    context = _format_docs(chunks)

    # Build history string if provided (capped at last 3 turns to protect RAM)
    history_text = ""
    if chat_history:
        recent = chat_history[-3:]
        history_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in recent
        )

    prompt_input = {
        "context": context,
        "question": question if not history_text else f"{history_text}\nUser: {question}",
    }

    chain = _RAG_PROMPT | llm | StrOutputParser()

    try:
        answer = _run_chain(chain, prompt_input)
    except (httpx.TimeoutException, requests.exceptions.Timeout) as exc:
        return {
            "answer": "Ollama took too long to respond.",
            "sources": [],
            "chunks_used": len(chunks),
            "chunks": chunks,
            "error_type": "ollama_timeout",
        }
    except Exception as exc:
        # Catch any other exception whose message mentions "timeout" as a
        # safety net for future transport changes.
        if "timeout" in str(exc).lower():
            return {
                "answer": "Ollama took too long to respond.",
                "sources": [],
                "chunks_used": len(chunks),
                "chunks": chunks,
                "error_type": "ollama_timeout",
            }
        raise

    # Only cite a source if at least one of its chunks had a strong vector match.
    # This prevents BM25-only keyword matches from irrelevant documents appearing as sources.
    _SOURCE_DISTANCE_THRESHOLD = 0.9
    sources = list({
        c["metadata"].get("file_name", "unknown")
        for c in chunks
        if c.get("distance") is not None and c["distance"] < _SOURCE_DISTANCE_THRESHOLD
    })
    # Fall back to all sources if the filter removes everything (e.g. all BM25-only results)
    if not sources:
        sources = list({c["metadata"].get("file_name", "unknown") for c in chunks})

    return {
        "answer": answer,
        "sources": sources,
        "chunks_used": len(chunks),
        "chunks": chunks,
        "error_type": None,
    }
