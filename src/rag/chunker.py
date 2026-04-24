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

    A line is treated as a heading if it is <= 80 chars and matches _HEADING_RE.
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
