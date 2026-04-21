from __future__ import annotations


RISK_KEYWORDS = {
    "Financial Risk": {
        "keywords": ["debt", "loss", "overdue", "unpaid", "deficit", "bankruptcy", "late payment"],
        "weight": 10,
        "min_hits": 1,
    },
    "Compliance Risk": {
        "keywords": ["violation", "breach", "non-compliant", "penalty", "legal action", "regulation"],
        "weight": 12,
        "min_hits": 1,
    },
    "Operational Risk": {
        "keywords": ["delay", "failure", "incident", "issue", "disruption", "error", "downtime"],
        "weight": 8,
        "min_hits": 2,
    },
    "Security Risk": {
        "keywords": ["leak", "unauthorized", "password", "confidential", "security breach", "malware"],
        "weight": 14,
        "min_hits": 1,
    },
    "Reputational Risk": {
        "keywords": ["complaint", "negative publicity", "customer dissatisfaction", "reputation", "fraud"],
        "weight": 9,
        "min_hits": 1,
    },
}


def calculate_risk(text: str) -> dict:
    if not text or not text.strip():
        return {
            "risk_score": 0,
            "risk_label": "Low",
            "risk_categories": [],
            "flagged_phrases": [],
        }

    lowered = text.lower()
    total_score = 0
    matched_categories = []
    flagged_phrases = []

    for category, rule in RISK_KEYWORDS.items():
        matches = [kw for kw in rule["keywords"] if kw in lowered]

        if len(matches) >= rule["min_hits"]:
            matched_categories.append(category)
            flagged_phrases.extend(matches)

            category_score = rule["weight"] + min(len(matches) - 1, 2) * 3
            total_score += category_score

    total_score = min(total_score, 85)

    if total_score >= 70:
        label = "Critical"
    elif total_score >= 50:
        label = "High"
    elif total_score >= 25:
        label = "Medium"
    else:
        label = "Low"

    return {
        "risk_score": total_score,
        "risk_label": label,
        "risk_categories": matched_categories,
        "flagged_phrases": sorted(set(flagged_phrases)),
    }