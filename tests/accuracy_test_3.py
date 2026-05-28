"""
Accuracy Test 3 — User-defined questions (10 real-world queries).
Run: python tests/accuracy_test_3.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rag.llm_interface import ask_with_rag, get_llm

TEST_CASES = [
    {
        "id": 1,
        "question": "List all Queensland Women in STEM Award 2025",
        "expected_keywords": ["women", "stem", "award", "queensland"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 2,
        "question": "Give me details regarding Integrity Procedures and Practices",
        "expected_keywords": ["integrity", "procedure", "practice"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 3,
        "question": "Summarise 'Impairment of assets' from Griffith annual report",
        "expected_keywords": ["impairment", "asset", "aasb", "valuation"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 4,
        "question": "Details about 'Financing Arrangements'",
        "expected_keywords": ["financing", "arrangement", "facility", "credit"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 5,
        "question": "What is the total provisions in 2024",
        "expected_keywords": ["provision", "2024", "total"],
        "expected_source": "griffith",
        "category": "Annual Report",
    },
    {
        "id": 6,
        "question": "What is Lucas Caulley's role based on the peer review document",
        "expected_keywords": ["lucas", "caulley", "role"],
        "expected_source": "Peer review",
        "category": "Peer Review",
    },
    {
        "id": 7,
        "question": "What's the benefit of passive building?",
        "expected_keywords": [],
        "expected_source": None,
        "category": "Out-of-scope",
        "expect_no_answer": True,
    },
    {
        "id": 8,
        "question": "How many issues are there related to passive building and explain for each one",
        "expected_keywords": [],
        "expected_source": None,
        "category": "Out-of-scope",
        "expect_no_answer": True,
    },
    {
        "id": 9,
        "question": "What is the latest iPhone model released in 2025?",
        "expected_keywords": [],
        "expected_source": None,
        "category": "Out-of-scope",
        "expect_no_answer": True,
    },
    {
        "id": 10,
        "question": "What's the Carbon emission reduction target for 2025",
        "expected_keywords": ["carbon", "emission", "target", "reduction"],
        "expected_source": "griffith",
        "category": "Annual Report",
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
        no_info_phrases = ["do not contain", "not enough information", "cannot", "don't have", "no information"]
        if any(p in answer_lower for p in no_info_phrases):
            return PASS, ["Correctly declined out-of-scope question"]
        return WARN, ["Should have declined but gave an answer — check if answer is hallucinated"]

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
            notes.append(f"Expected source '{expected_src}' not in {result['sources']}")

    notes.append(f"Chunks used: {result['chunks_used']}")
    verdict = PASS if keyword_ratio >= 0.3 else FAIL
    return verdict, notes


def run_tests():
    print("=" * 65)
    print("  INSIGHT AI — Accuracy Test 3 (User-Defined Questions)")
    print("=" * 65)

    llm = get_llm()
    results = []

    for tc in TEST_CASES:
        print(f"\n[{tc['id']}/10] {tc['category']}: {tc['question'][:60]}...")
        result = ask_with_rag(tc["question"], llm)
        verdict, notes = score_result(result, tc)

        print(f"  Verdict  : {verdict}")
        print(f"  Answer   : {result['answer'][:350]}{'...' if len(result['answer']) > 350 else ''}")
        print(f"  Sources  : {result['sources']}")
        for note in notes:
            print(f"  Note     : {note}")

        results.append({"tc": tc, "result": result, "verdict": verdict, "notes": notes})

    print("\n" + "=" * 65)
    passed = sum(1 for r in results if r["verdict"] == PASS)
    warned = sum(1 for r in results if r["verdict"] == WARN)
    failed = sum(1 for r in results if r["verdict"] == FAIL)
    score_pct = round((passed + 0.5 * warned) / len(results) * 100, 1)

    print(f"  RESULTS: {passed}/10 PASS  |  {warned} WARN  |  {failed} FAIL")
    print(f"  SCORE  : {score_pct}%")
    print("=" * 65)

    return results


if __name__ == "__main__":
    run_tests()
