from __future__ import annotations

import re
from collections import Counter


STOPWORDS = {
    "the", "and", "is", "in", "to", "of", "for", "on", "a", "an", "by", "with",
    "this", "that", "it", "as", "at", "from", "or", "be", "are", "was", "were",
    "has", "have", "had", "but", "not", "we", "they", "their", "our", "can",
    "will", "would", "should", "could", "into", "about", "after", "before",
    "than", "then", "if", "no", "yes", "such", "these", "those", "you", "your",
    "use", "used", "using", "report", "internal", "document", "documents",
    "file", "files", "page", "table", "contents", "summary", "including",
    "which", "within", "through", "across", "based", "related", "regarding",
    "level", "levels", "employees", "employee", "staff", "community", "council",
    "city", "process", "services", "service", "program", "programs", "division",
    "review", "assessment", "results", "result", "information", "product",
    "provided", "provide", "provided", "ability", "objective", "objectives"
}

LOW_VALUE_TERMS = {
    "community", "council", "employees", "staff", "level", "levels", "including",
    "which", "process", "city", "program", "services", "division"
}

BUSINESS_PRIORITY = {
    "risk", "risks", "compliance", "security", "breach", "confidential",
    "audit", "control", "controls", "financial", "incident", "fraud",
    "violation", "policy", "governance", "operations", "reporting",
    "mitigation", "likelihood", "impact", "preparedness", "trajectory",
    "reputation", "debt", "loss", "regulation", "unauthorized", "password"
}


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-zA-Z][a-zA-Z0-9\-]{2,}\b", text.lower())


def normalize_token(token: str) -> str:
    token = token.strip("-")
    return token


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    if not text or not text.strip():
        return []

    words = tokenize(text)

    filtered = []
    for word in words:
        word = normalize_token(word)

        if not word:
            continue
        if len(word) < 4:
            continue
        if word in STOPWORDS:
            continue
        if word.isdigit():
            continue

        filtered.append(word)

    counts = Counter(filtered)

    # tăng điểm cho từ có giá trị business/risk
    for word in list(counts.keys()):
        if word in BUSINESS_PRIORITY:
            counts[word] += 4
        if word in LOW_VALUE_TERMS:
            counts[word] -= 2

    # bỏ các từ điểm <= 0
    cleaned_counts = {word: count for word, count in counts.items() if count > 0}

    # ưu tiên unique meaningful keywords
    ranked = sorted(cleaned_counts.items(), key=lambda x: x[1], reverse=True)

    keywords = []
    seen_roots = set()

    for word, _ in ranked:
        root = word.rstrip("s")
        if root in seen_roots:
            continue
        seen_roots.add(root)
        keywords.append(word)

        if len(keywords) >= top_n:
            break

    return keywords