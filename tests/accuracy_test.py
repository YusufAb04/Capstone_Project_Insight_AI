"""
Accuracy test for INSIGHT AI RAG pipeline.
Tests retrieval + answer quality across the 3 indexed documents.
Run: python tests/accuracy_test.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rag.llm_interface import ask_with_rag, get_llm

# ── Test cases (question, expected_keywords, expected_source_fragment) ──────
TEST_CASES = [
    # Essential Eight
    {
        "question": "What are the Essential Eight cybersecurity strategies?",
        "expected_keywords": ["patch", "application", "control", "backup", "multi-factor"],
        "expected_source": "Essential Eight",
        "category": "Essential Eight",
    },
    {
        "question": "What maturity level requirements exist for patching applications?",
        "expected_keywords": ["maturity", "patch", "level", "vulnerability"],
        "expected_source": "Essential Eight",
        "category": "Essential Eight",
    },
    {
        "question": "What evidence is required for multi-factor authentication compliance?",
        "expected_keywords": ["authentication", "evidence", "multi-factor", "mfa"],
        "expected_source": "Essential Eight",
        "category": "Essential Eight",
    },
    # Griffith University Annual Report
    {
        "question": "What were Griffith University's key achievements in 2025?",
        "expected_keywords": ["griffith", "university", "research", "students"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "question": "How many students are enrolled at Griffith University?",
        "expected_keywords": ["student", "enrol"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    # Peer Review
    {
        "question": "What is the main feedback given in the peer review?",
        "expected_keywords": ["review", "feedback", "research", "paper"],
        "expected_source": "Peer review",
        "category": "Peer Review",
    },
    # Cross-document
    {
        "question": "What security controls are recommended for organisations?",
        "expected_keywords": ["control", "security", "risk"],
        "expected_source": "Essential Eight",
        "category": "Cross-doc",
    },
    # Out-of-scope (should gracefully decline)
    {
        "question": "What is the weather forecast for Brisbane tomorrow?",
        "expected_keywords": [],
        "expected_source": None,
        "category": "Out-of-scope",
        "expect_no_answer": True,
    },
]

PASS  = "PASS"
FAIL  = "FAIL"
WARN  = "WARN"


def score_result(result: dict, tc: dict) -> tuple[str, list[str]]:
    notes = []

    # Error check
    if result["error_type"] in ("no_chunks", "ollama_timeout"):
        if tc.get("expect_no_answer"):
            return PASS, ["Correctly returned no answer"]
        return FAIL, [f"Error: {result['error_type']}"]

    answer_lower = result["answer"].lower()

    # Out-of-scope: should say it doesn't have info
    if tc.get("expect_no_answer"):
        no_info_phrases = ["do not contain", "not enough information", "cannot", "don't have"]
        if any(p in answer_lower for p in no_info_phrases):
            return PASS, ["Correctly declined out-of-scope question"]
        return WARN, ["Should have declined but gave an answer"]

    # Keyword check
    keywords = tc.get("expected_keywords", [])
    matched = [kw for kw in keywords if kw in answer_lower]
    keyword_ratio = len(matched) / len(keywords) if keywords else 1.0
    if keyword_ratio < 0.3:
        notes.append(f"Low keyword match: {matched}/{keywords}")
    else:
        notes.append(f"Keywords matched: {matched}")

    # Source check
    expected_src = tc.get("expected_source")
    if expected_src:
        src_lower = expected_src.lower()
        sources_lower = [s.lower() for s in result["sources"]]
        if any(src_lower in s for s in sources_lower):
            notes.append(f"Correct source cited")
        else:
            notes.append(f"Expected source '{expected_src}' not cited (got: {result['sources']})")

    # Chunks check
    notes.append(f"Chunks used: {result['chunks_used']}")

    verdict = PASS if keyword_ratio >= 0.3 else FAIL
    return verdict, notes


def run_tests():
    print("=" * 65)
    print("  INSIGHT AI — RAG Accuracy Test")
    print("=" * 65)

    llm = get_llm()
    results = []

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {tc['category']}: {tc['question'][:60]}...")
        result = ask_with_rag(tc["question"], llm)
        verdict, notes = score_result(result, tc)

        print(f"  Verdict  : {verdict}")
        print(f"  Answer   : {result['answer'][:200]}{'...' if len(result['answer']) > 200 else ''}")
        print(f"  Sources  : {result['sources']}")
        for note in notes:
            print(f"  Note     : {note}")

        results.append({"tc": tc, "result": result, "verdict": verdict})

    # Summary
    print("\n" + "=" * 65)
    passed = sum(1 for r in results if r["verdict"] == PASS)
    warned = sum(1 for r in results if r["verdict"] == WARN)
    failed = sum(1 for r in results if r["verdict"] == FAIL)
    total  = len(results)

    print(f"  RESULTS: {passed}/{total} PASS  |  {warned} WARN  |  {failed} FAIL")
    score_pct = round((passed + 0.5 * warned) / total * 100, 1)
    print(f"  SCORE  : {score_pct}%")
    print("=" * 65)

    return passed, warned, failed


if __name__ == "__main__":
    run_tests()
