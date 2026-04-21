from __future__ import annotations


DOCUMENT_RULES = {
    "Invoice": [
        "invoice", "amount due", "bill to", "payment", "tax invoice", "subtotal",
        "total", "gst", "remittance", "due date"
    ],
    "Contract": [
        "agreement", "contract", "terms and conditions", "party", "obligation",
        "liability", "clause", "termination", "binding"
    ],
    "Policy": [
        "policy", "procedure", "guideline", "compliance", "standard",
        "regulation", "framework", "control"
    ],
    "Meeting Notes": [
        "meeting", "agenda", "minutes", "attendees", "discussion",
        "action items", "next steps", "decisions"
    ],
    "HR Document": [
        "employee", "recruitment", "leave", "salary", "performance review",
        "hr", "staff", "onboarding", "termination"
    ],
    "Financial Record": [
        "revenue", "expense", "profit", "loss", "budget", "forecast",
        "balance", "financial", "audit", "cash flow"
    ],
    "Report": [
        "report", "analysis", "summary", "findings", "overview",
        "recommendation", "assessment", "executive summary"
    ],
    "Security Document": [
        "security", "incident", "password", "unauthorized", "breach",
        "cyber", "malware", "confidential"
    ],
}


def classify_document(text: str) -> str:
    if not text or not text.strip():
        return "Unknown"

    lowered = text.lower()
    scores = {}

    for doc_type, keywords in DOCUMENT_RULES.items():
        score = 0
        for keyword in keywords:
            if keyword in lowered:
                score += 1
        scores[doc_type] = score

    best_type = max(scores, key=scores.get)
    return best_type if scores[best_type] > 0 else "General Business File"