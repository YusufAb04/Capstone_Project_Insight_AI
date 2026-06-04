from __future__ import annotations

import re
from collections import Counter


IMPORTANT_TERMS = {
    "risk", "compliance", "issue", "incident", "management", "recommendation",
    "security", "financial", "breach", "policy", "control", "audit",
    "confidential", "fraud", "loss", "delay", "failure", "violation",
    "assessment", "mitigation", "governance", "operations", "reporting"
}

GENERIC_NOISE_TERMS = {
    "moderate-to-high", "low-to-moderate", "flat", "increasing", "decreasing",
    "city", "community", "council", "employees", "staff", "level", "levels"
}


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def split_into_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []

    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    sentences = [c.strip() for c in chunks if c.strip()]
    return sentences


def is_bad_sentence(sentence: str) -> bool:
    lowered = sentence.lower().strip()
    words = lowered.split()

    if len(words) < 8:
        return True

    if len(words) > 60:
        return True

    if re.fullmatch(r"[A-Z0-9\s\-/,:()]+", sentence) and len(words) < 20:
        return True

    if sum(1 for term in GENERIC_NOISE_TERMS if term in lowered) >= 3:
        return True

    if re.search(r"\b\d{1,3}%\b", lowered):
        return True

    if re.search(r"\bpage\s+\d+\b", lowered):
        return True

    # line resembles a risk matrix table row
    if "moderate-to-high" in lowered and "low-to-moderate" in lowered:
        return True

    # too many hyphens typical of table formatting
    if sentence.count("-") >= 4:
        return True

    return False


def score_sentence(sentence: str, word_freq: Counter) -> float:
    lowered = sentence.lower()
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9\-]{2,}\b", lowered)

    if not words:
        return 0.0

    score = 0.0

    for word in words:
        score += word_freq.get(word, 0)

    important_hits = sum(1 for term in IMPORTANT_TERMS if term in lowered)
    score += important_hits * 4

    # prefer sentences of moderate length
    if 12 <= len(words) <= 30:
        score += 3

    # prefer sentences containing action or evaluation meaning
    action_patterns = [
        "includes",
        "identifies",
        "recommends",
        "assesses",
        "evaluates",
        "high risk",
        "moderate risk",
        "low risk",
        "mitigate",
        "monitor",
    ]
    score += sum(2 for p in action_patterns if p in lowered)

    return score


def summarize_text(text: str, max_sentences: int = 3) -> str:
    if not text or not text.strip():
        return "No summary available."

    sentences = split_into_sentences(text)
    sentences = [s for s in sentences if not is_bad_sentence(s)]

    if not sentences:
        return "No summary available."

    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9\-]{2,}\b", text.lower())
    freq = Counter(words)

    scored = [(sentence, score_sentence(sentence, freq)) for sentence in sentences]
    scored.sort(key=lambda x: x[1], reverse=True)

    selected = [s for s, _ in scored[:max_sentences]]

    # preserve original sentence order
    ordered_selected = [s for s in sentences if s in selected]

    if not ordered_selected:
        return "No summary available."

    return " ".join(ordered_selected)