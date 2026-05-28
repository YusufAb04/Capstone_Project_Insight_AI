from __future__ import annotations

import hashlib
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""],
)

_HEADING_RE = re.compile(
    r'^(?:'
    r'\d+(?:\.\d+)*\.?\s+\S.{0,69}'                       # numbered: "1. Foo", "2.3 Bar"
    r'|[A-Z][A-Z0-9 &/\-]{3,58}[A-Z0-9]'                  # ALL CAPS: "NATURAL DISASTER"
    r'|(?:[A-Z][a-z]{1,20})(?:\s[A-Z][a-z]{1,20}){1,6}'   # Title Case: "Natural Disaster"
    r')$'
)

# Max chars per table sub-chunk before splitting at a row boundary
_TABLE_CHUNK_MAX = 480


def _file_id_prefix(file_path: str) -> str:
    """Short deterministic prefix derived from the file path."""
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

    return sections


def _split_body(body: str, heading: str) -> list[str]:
    """Chunk body text, keeping [Table] blocks intact at row boundaries.

    Prose paragraphs are split with _SPLITTER. Table blocks (lines starting
    with '[Table]') are kept as whole chunks or split only between rows so
    that no individual row is cut mid-cell.
    """
    prefix = f"[Section: {heading}]\n" if heading else ""
    chunks: list[str] = []
    prose_buf: list[str] = []

    def _flush_prose() -> None:
        if prose_buf:
            joined = "\n\n".join(prose_buf)
            for raw in _SPLITTER.split_text(joined):
                chunks.append(f"{prefix}{raw}" if prefix else raw)
            prose_buf.clear()

    for para in re.split(r'\n{2,}', body):
        stripped = para.strip()
        if not stripped:
            continue

        if stripped.startswith('[Table]'):
            _flush_prose()
            lines = stripped.split('\n')
            col_header = lines[1] if len(lines) > 1 else ""
            data_rows = lines[2:] if len(lines) > 2 else []

            if len(stripped) <= _TABLE_CHUNK_MAX:
                chunks.append(f"{prefix}{stripped}" if prefix else stripped)
            else:
                # Split at row boundaries; repeat column header in every sub-chunk
                current = ['[Table]']
                if col_header:
                    current.append(col_header)
                current_size = sum(len(r) for r in current) + len(current)

                for row in data_rows:
                    row_len = len(row) + 1
                    if current_size + row_len > _TABLE_CHUNK_MAX and len(current) > (2 if col_header else 1):
                        block = "\n".join(current)
                        chunks.append(f"{prefix}{block}" if prefix else block)
                        current = ['[Table]']
                        if col_header:
                            current.append(col_header)
                        current_size = sum(len(r) for r in current) + len(current)
                    current.append(row)
                    current_size += row_len

                if len(current) > 1:
                    block = "\n".join(current)
                    chunks.append(f"{prefix}{block}" if prefix else block)
        else:
            prose_buf.append(stripped)

    _flush_prose()
    return chunks


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
            if heading:
                chunks.append({
                    "id": f"{prefix}::chunk_{chunk_idx}",
                    "text": f"[Section: {heading}]",
                    "metadata": {
                        "file_path": file_path,
                        "file_name": file_name,
                        "chunk_index": chunk_idx,
                        "total_chunks": 0,
                        "section_heading": heading,
                    },
                })
                chunk_idx += 1
            continue
        for text_val in _split_body(body, heading):
            chunks.append({
                "id": f"{prefix}::chunk_{chunk_idx}",
                "text": text_val,
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
