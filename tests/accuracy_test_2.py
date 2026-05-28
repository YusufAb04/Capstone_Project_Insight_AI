"""
Accuracy Test 2 — INSIGHT AI RAG pipeline (no table-heavy documents).
Indexed: Griffith University Annual Report 2025 + Peer Review (Muhammad Budiman).
Run: python tests/accuracy_test_2.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rag.llm_interface import ask_with_rag, get_llm

TEST_CASES = [
    # ── Annual Report ─────────────────────────────────────────────────────────
    {
        "id": 1,
        "question": "What were Griffith University's key achievements in 2025?",
        "expected_keywords": ["griffith", "university", "research", "ranked"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 2,
        "question": "What is Griffith University's global sustainability ranking in 2025?",
        "expected_keywords": ["sustainability", "ranking", "qs", "top"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 3,
        "question": "How many students are enrolled at Griffith University?",
        "expected_keywords": ["student", "enrol"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 4,
        "question": "What campuses does Griffith University operate?",
        "expected_keywords": ["campus", "gold coast", "nathan", "brisbane"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 5,
        "question": "Who is the Vice-Chancellor of Griffith University?",
        "expected_keywords": ["vice-chancellor", "chancellor", "professor"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 6,
        "question": "What are Griffith University's main research focus areas?",
        "expected_keywords": ["research", "health", "environment", "innovation"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 7,
        "question": "What is Griffith University's financial performance or total revenue in 2025?",
        "expected_keywords": ["revenue", "financial", "million", "income"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    # ── Peer Review ───────────────────────────────────────────────────────────
    {
        "id": 8,
        "question": "What is the main feedback given in the peer review for Muhammad Budiman?",
        "expected_keywords": ["review", "feedback", "budiman", "contribution"],
        "expected_source": "Peer review",
        "category": "Peer Review",
    },
    {
        "id": 9,
        "question": "What specific skills or qualities are highlighted in the peer review?",
        "expected_keywords": ["skill", "quality", "team", "reliable"],
        "expected_source": "Peer review",
        "category": "Peer Review",
    },
    # ── Out-of-scope ──────────────────────────────────────────────────────────
    {
        "id": 10,
        "question": "What is the latest iPhone model released in 2025?",
        "expected_keywords": [],
        "expected_source": None,
        "category": "Out-of-scope",
        "expect_no_answer": True,
    },
]

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


def score_result(result: dict, tc: dict) -> tuple[str, list[str]]:
    notes = []

    if result["error_type"] in ("no_chunks", "ollama_timeout"):
        if tc.get("expect_no_answer"):
            return PASS, ["Correctly returned no answer"]
        return FAIL, [f"Error: {result['error_type']}"]

    answer_lower = result["answer"].lower()

    if tc.get("expect_no_answer"):
        no_info_phrases = ["do not contain", "not enough information", "cannot", "don't have"]
        if any(p in answer_lower for p in no_info_phrases):
            return PASS, ["Correctly declined out-of-scope question"]
        return WARN, ["Should have declined but gave an answer"]

    keywords = tc.get("expected_keywords", [])
    matched = [kw for kw in keywords if kw in answer_lower]
    keyword_ratio = len(matched) / len(keywords) if keywords else 1.0
    if keyword_ratio < 0.3:
        notes.append(f"Low keyword match: {matched} / expected {keywords}")
    else:
        notes.append(f"Keywords matched: {matched}")

    expected_src = tc.get("expected_source")
    if expected_src:
        sources_lower = [s.lower() for s in result["sources"]]
        if any(expected_src.lower() in s for s in sources_lower):
            notes.append("Correct source cited")
        else:
            notes.append(f"Expected source '{expected_src}' not cited (got: {result['sources']})")

    notes.append(f"Chunks used: {result['chunks_used']}")

    verdict = PASS if keyword_ratio >= 0.3 else FAIL
    return verdict, notes


def run_tests():
    print("=" * 65)
    print("  INSIGHT AI — Accuracy Test 2 (No Table-Format Documents)")
    print("=" * 65)

    llm = get_llm()
    results = []

    for tc in TEST_CASES:
        print(f"\n[{tc['id']}/10] {tc['category']}: {tc['question'][:60]}...")
        result = ask_with_rag(tc["question"], llm)
        verdict, notes = score_result(result, tc)

        print(f"  Verdict  : {verdict}")
        print(f"  Answer   : {result['answer'][:300]}{'...' if len(result['answer']) > 300 else ''}")
        print(f"  Sources  : {result['sources']}")
        for note in notes:
            print(f"  Note     : {note}")

        results.append({"tc": tc, "result": result, "verdict": verdict, "notes": notes})

    print("\n" + "=" * 65)
    passed = sum(1 for r in results if r["verdict"] == PASS)
    warned = sum(1 for r in results if r["verdict"] == WARN)
    failed = sum(1 for r in results if r["verdict"] == FAIL)
    total  = len(results)
    score_pct = round((passed + 0.5 * warned) / total * 100, 1)

    print(f"  RESULTS: {passed}/{total} PASS  |  {warned} WARN  |  {failed} FAIL")
    print(f"  SCORE  : {score_pct}%")
    print("=" * 65)

    return results


if __name__ == "__main__":
    run_tests()
