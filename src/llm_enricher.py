from __future__ import annotations

_MAX_WORDS = 1500

_PROMPT_TEMPLATE = (
    "Analyse this document and respond in exactly this format — no extra text:\n"
    "SUMMARY: <2-3 sentence plain-English summary>\n"
    "TYPE: <one of: Invoice / Contract / Policy / Meeting Notes / HR Document"
    " / Financial Record / Report / Security Document / General Business File>\n"
    "RISK: <1-2 sentences explaining the main risks,"
    ' or "No significant risks identified." if low risk>\n'
    "TAKEAWAY: <1-2 sentences for an executive>\n\n"
    "Risk level assessed by rules: {risk_label}\n\n"
    "Document (may be truncated):\n{text}"
)

_PREFIX_TO_KEY = {
    "SUMMARY:": "summary",
    "TYPE:": "document_type",
    "RISK:": "risk_explanation",
    "TAKEAWAY:": "management_takeaway",
}

_REQUIRED_KEYS = {"summary", "document_type", "risk_explanation", "management_takeaway"}


def enrich_with_llm(content: str, risk_label: str, llm) -> dict | None:
    words = content.split()
    text = " ".join(words[:_MAX_WORDS]) if len(words) > _MAX_WORDS else content
    prompt = _PROMPT_TEMPLATE.format(risk_label=risk_label, text=text)
    try:
        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
    except Exception:
        return None
    return _parse_response(raw)


def _parse_response(raw: str) -> dict | None:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        for prefix, key in _PREFIX_TO_KEY.items():
            if line.startswith(prefix):
                result[key] = line[len(prefix):].strip()
                break
    if result.keys() == _REQUIRED_KEYS:
        return result
    return None
