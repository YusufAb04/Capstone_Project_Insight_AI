from __future__ import annotations

import requests

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from src.rag.vector_store import similarity_search

_RAG_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a document analyst for an organisation's internal document library. "
        "Answer the user's question using ONLY the context provided below. "
        "If the context does not contain enough information to answer, say: "
        "'The indexed documents do not contain enough information to answer this question.' "
        "Always cite the source document file name when referencing specific information.\n\n"
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


def ask_with_rag(
    question: str,
    llm: ChatOllama,
    persist_dir: str = "data/chromadb",
    top_k: int = 4,
    chat_history: list[dict] | None = None,
) -> dict:
    """Run a RAG query and return the answer with source references.

    Returns:
        answer       — LLM-generated answer string
        sources      — list of unique file names cited
        chunks_used  — number of chunks retrieved
        chunks       — raw chunk dicts (for UI display)
    """
    chunks = similarity_search(question, top_k=top_k, persist_dir=persist_dir)

    if not chunks:
        return {
            "answer": "No documents have been indexed yet. Please ingest some files via the Ingestion Hub first.",
            "sources": [],
            "chunks_used": 0,
            "chunks": [],
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
    answer = chain.invoke(prompt_input)

    sources = list({c["metadata"].get("file_name", "unknown") for c in chunks})

    return {
        "answer": answer,
        "sources": sources,
        "chunks_used": len(chunks),
        "chunks": chunks,
    }
