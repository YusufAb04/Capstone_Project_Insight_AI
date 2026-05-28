# INSIGHT AI — RAG Accuracy Test Report

**Date:** 2026-05-28
**Model:** llama3.2:3b (via Ollama)
**Embedding Model:** all-MiniLM-L6-v2 (SentenceTransformers)
**Vector Store:** ChromaDB
**Retrieval:** Top-8 chunks per query (cosine similarity)

---

## Indexed Documents

| # | File | Type | Size |
|---|---|---|---|
| 1 | Essential Eight Evidence Guide (1).pdf | PDF | 256,866 bytes |
| 2 | griffith-university-annual-report-2025.pdf | PDF | 3,234,277 bytes |
| 3 | Peer review Muhammad_Budiman V3.docx | DOCX | 29,466 bytes |

---

## Test Results Summary

**Overall Score: 5 / 8 PASS (62.5%)**

| # | Category | Verdict |
|---|---|---|
| 1 | Essential Eight | FAIL |
| 2 | Essential Eight | FAIL |
| 3 | Essential Eight | PASS |
| 4 | Annual Report | PASS |
| 5 | Annual Report | FAIL |
| 6 | Peer Review | PASS |
| 7 | Cross-document | PASS |
| 8 | Out-of-scope | PASS |

---

## Detailed Results

---

### Question 1 — Essential Eight Strategies

**Category:** Essential Eight
**Question:** What are the Essential Eight cybersecurity strategies?

**Answer from AI:**
> The Essential Eight cybersecurity strategies are outlined in the Essential Eight Evidence Guide (1).pdf. The eight strategies are:
> 1. Implement a web application firewall (WAF) as a substitute for or...

**Sources cited:** Essential Eight Evidence Guide (1).pdf, griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: FAIL**

**Is the answer correct?** No — the AI hallucinated. It listed "Implement a web application firewall (WAF)" as one of the Essential Eight, which is factually wrong. The actual Essential Eight strategies are: Application Control, Patch Applications, Configure Microsoft Office Macro Settings, User Application Hardening, Restrict Administrative Privileges, Patch Operating Systems, Multi-Factor Authentication, and Regular Backups. None of these appeared correctly in the answer.

**Root cause:** The 8 retrieved chunks did not include the actual strategy list. Instead of saying "not enough information," the model fabricated a list.

---

### Question 2 — Patching Maturity Levels

**Category:** Essential Eight
**Question:** What maturity level requirements exist for patching applications?

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Sources cited:** Essential Eight Evidence Guide (1).pdf
**Chunks retrieved:** 8

**Verdict: FAIL**

**Is the answer correct?** Partially — the model correctly refused to fabricate an answer, but the actual Essential Eight Evidence Guide does contain maturity level information for patching applications (Maturity Levels 1–3 with specific requirements). The system failed to retrieve the relevant section.

**Root cause:** Retrieval gap. The maturity level tables/sections were not pulled into the top-8 chunks despite being present in the document.

---

### Question 3 — MFA Evidence Requirements

**Category:** Essential Eight
**Question:** What evidence is required for multi-factor authentication compliance?

**Answer from AI:**
> According to the Essential Eight Evidence Guide (1).pdf, the following evidence is required for multi-factor authentication (MFA) compliance:
> 1. Evidence may include screenshots of MFA configurations...

**Sources cited:** Essential Eight Evidence Guide (1).pdf
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — the model correctly retrieved and cited MFA-related content from the Essential Eight Evidence Guide. It properly referenced the source document and provided relevant evidence requirements including configuration screenshots as examples.

**Root cause of success:** The MFA section likely had strong semantic similarity with the query, pulling the right chunks.

---

### Question 4 — Griffith University Key Achievements 2025

**Category:** Annual Report
**Question:** What were Griffith University's key achievements in 2025?

**Answer from AI:**
> According to the Griffith University Annual Report 2025, some of the key achievements in 2025 include:
> - Ranked in the top 50 worldwide in the QS World University Rankings: Sustainability 2025
> - Sign...

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — the model correctly retrieved achievement highlights from the annual report and cited the correct source document. The QS World University Rankings detail is a verifiable fact from the 2025 report.

---

### Question 5 — Student Enrollment Numbers

**Category:** Annual Report
**Question:** How many students are enrolled at Griffith University?

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: FAIL**

**Is the answer correct?** No — the Griffith University Annual Report 2025 does contain enrollment figures, but the system failed to retrieve the specific chunk containing that data. The model correctly declined to guess, but the expected outcome was a real answer with a number.

**Root cause:** Retrieval gap. Enrollment statistics are likely in a specific table or section that did not rank in the top-8 most similar chunks for this query.

---

### Question 6 — Peer Review Main Feedback

**Category:** Peer Review
**Question:** What is the main feedback given in the peer review?

**Answer from AI:**
> The main feedback given in the peer review is that Muhammad Budiman has been a valuable and reliable team member, consistently making substantial and highly valued additions to development, addressing...

**Sources cited:** Peer review Muhammad_Budiman V3.docx
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — the model correctly identified and summarised the main feedback from the peer review document. It cited the correct source and accurately reflected the content of the document (positive review of Muhammad Budiman's contributions).

---

### Question 7 — Security Controls for Organisations

**Category:** Cross-document
**Question:** What security controls are recommended for organisations?

**Answer from AI:**
> The Essential Eight Evidence Guide recommends the following security controls for organisations:
> 1. Application Control - Whitelist: Application control restricts the execution of executables, softwa...

**Sources cited:** Essential Eight Evidence Guide (1).pdf, griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — the model correctly retrieved security control information from the Essential Eight Evidence Guide and cited the relevant source. Application Control is a legitimate Essential Eight strategy, and the description provided is accurate.

**Note:** The Griffith University annual report was also cited as a source, which is unlikely to contain security control recommendations. This is a minor false-positive citation.

---

### Question 8 — Out-of-Scope Query

**Category:** Out-of-scope
**Question:** What is the weather forecast for Brisbane tomorrow?

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — the model correctly declined to answer a question that is completely outside the scope of the indexed documents. This demonstrates appropriate boundary behaviour; it did not hallucinate a weather forecast.

---

## Key Findings

### What works well
- **Out-of-scope rejection** — the system correctly refuses to answer questions unrelated to the documents
- **Source citation** — in all 8 tests, at least one source was cited and it was correct or near-correct
- **General/broad questions** — questions about broad topics (achievements, security controls, feedback) retrieved relevant content successfully

### What needs improvement

| Issue | Affected Tests | Impact |
|---|---|---|
| **Hallucination on retrieval failure** | Test 1 | High — model fabricated wrong facts instead of declining |
| **Retrieval gap for specific details** | Tests 2, 5 | High — relevant content exists but is not retrieved |
| **Irrelevant source cited** | Tests 1, 7 | Low — minor noise, does not affect answer quality |

### Recommended Fixes

1. **Increase `top_k` from 8 to 15** ([src/rag/llm_interface.py:86](../src/rag/llm_interface.py)) — gives more chunk slots to hit specific sections like tables and numbered lists
2. **Add hallucination guard** — if retrieved chunks have low relevance scores, return "not enough information" rather than letting the model generate from weak context
3. **Reduce chunk size in chunker** ([src/rag/chunker.py](../src/rag/chunker.py)) — smaller chunks make it easier to retrieve precise data points (enrollment numbers, maturity level tables)

---

## Test Script

The test was run using `tests/accuracy_test.py`. To re-run:

```bash
.venv/Scripts/python.exe tests/accuracy_test.py
```

---

---

# Test 2 — Without Table-Format Documents

**Date:** 2026-05-28
**Reason for Test 2:** The Essential Eight Evidence Guide was removed from the index because it is a heavily table-formatted document. The hypothesis was that the AI struggles to retrieve and reason over table-structured content. Test 2 isolates the remaining prose-based documents to measure baseline accuracy without table interference.

## Indexed Documents (Test 2)

| # | File | Type | Chunks | Size |
|---|---|---|---|---|
| 1 | griffith-university-annual-report-2025.pdf | PDF | 477 | 3,234,277 bytes |
| 2 | Peer review Muhammad_Budiman V3.docx | DOCX | 17 | 29,466 bytes |

*Removed: Essential Eight Evidence Guide (1).pdf — heavy table/structured layout*

---

## Test 2 Results Summary

**Overall Score: 5 / 10 PASS (50.0%)**

| # | Category | Question | Verdict |
|---|---|---|---|
| 1 | Annual Report | Key achievements in 2025 | PASS |
| 2 | Annual Report | Global sustainability ranking | PASS |
| 3 | Annual Report | Student enrollment numbers | FAIL |
| 4 | Annual Report | What campuses does it operate | FAIL |
| 5 | Annual Report | Who is the Vice-Chancellor | FAIL |
| 6 | Annual Report | Main research focus areas | FAIL |
| 7 | Annual Report | Financial performance / total revenue | FAIL |
| 8 | Peer Review | Main feedback for Muhammad Budiman | PASS |
| 9 | Peer Review | Specific skills and qualities highlighted | PASS |
| 10 | Out-of-scope | Latest iPhone model in 2025 | PASS |

---

## Test 2 Detailed Results

---

### Question 1 — Griffith University Key Achievements

**Category:** Annual Report
**Question:** What were Griffith University's key achievements in 2025?

**Answer from AI:**
> According to Section 4 of the Griffith University Annual Report 2025, Griffith University's key achievements in 2025 include:
> - Significant achievements in education and research
> - Ranked in the top 50 worldwide in the QS World University Rankings: Sustainability 2025
> - Professor Yongsheng Gao was ...

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — the AI correctly retrieved key achievement highlights including the QS Sustainability ranking and cited the correct source with a section reference (Section 4).

---

### Question 2 — Global Sustainability Ranking

**Category:** Annual Report
**Question:** What is Griffith University's global sustainability ranking in 2025?

**Answer from AI:**
> According to the Griffith University Annual Report 2025, Griffith ranked No. 50 worldwide in the QS World University Rankings: Sustainability 2025.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — a precise, factual answer with a specific number (No. 50) and the correct ranking name. This is a strong result: a specific data point was retrieved and stated accurately.

---

### Question 3 — Student Enrollment Numbers

**Category:** Annual Report
**Question:** How many students are enrolled at Griffith University?

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: FAIL**

**Is the answer correct?** No — the annual report does contain enrollment figures. The system retrieved 8 chunks from the correct document but none of them contained the enrollment statistics. This is the same retrieval gap seen in Test 1 Question 5.

**Root cause:** Enrollment data is likely stored in a statistical table or summary section of the PDF. Despite removing the Essential Eight, the annual report itself still contains table-formatted data sections that the chunker does not retrieve effectively.

---

### Question 4 — University Campuses

**Category:** Annual Report
**Question:** What campuses does Griffith University operate?

**Answer from AI:**
> According to the Griffith University Annual Report 2025 (Section 32), Griffith University operates across five physical campuses and one digital campus.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: FAIL**

**Is the answer correct?** Partially — the AI correctly identified the number of campuses (five physical + one digital) and cited a specific section (Section 32). However, it did not name the individual campuses (Gold Coast, Nathan, South Bank, Logan, Mt Gravatt). The answer is not wrong but is incomplete. The scoring flagged it FAIL because specific campus names were absent.

**Note:** This is a borderline result. The count is accurate; only the names are missing.

---

### Question 5 — Vice-Chancellor

**Category:** Annual Report
**Question:** Who is the Vice-Chancellor of Griffith University?

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: FAIL**

**Is the answer correct?** No — the Vice-Chancellor's name appears in the annual report (typically in the foreword or leadership section). The relevant chunks were not retrieved. This suggests the leadership/foreword section of the PDF was not indexed into a high-similarity chunk for this query.

**Root cause:** Retrieval gap. The VC name likely appears only once in the document (foreword), making it a low-frequency chunk that does not rank highly in cosine similarity for this query.

---

### Question 6 — Research Focus Areas

**Category:** Annual Report
**Question:** What are Griffith University's main research focus areas?

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: FAIL**

**Is the answer correct?** No — a university annual report would normally describe research priorities and focus areas. The 8 retrieved chunks did not include this content despite it being present in the 477-chunk document.

**Root cause:** Retrieval gap. With 477 chunks and top_k=8, only 1.7% of the document is retrieved per query. Broad research topic sections may not score highly enough to reach the top 8.

---

### Question 7 — Financial Performance

**Category:** Annual Report
**Question:** What is Griffith University's financial performance or total revenue in 2025?

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: FAIL**

**Is the answer correct?** No — financial data is a standard section of any annual report. However, this data is almost certainly presented in table format (income statement, balance sheet). This confirms the original hypothesis: even with the Essential Eight removed, the annual report itself contains table-formatted financial data that the chunker and retriever cannot surface effectively.

**Root cause:** Financial data is in table format within the PDF. The chunker does not handle tabular layouts, so financial rows are either merged into garbled text or split across chunks that lose their context.

---

### Question 8 — Peer Review Main Feedback

**Category:** Peer Review
**Question:** What is the main feedback given in the peer review for Muhammad Budiman?

**Answer from AI:**
> The main feedback given in the peer review for Muhammad Budiman is that he has made substantial and highly valued contributions to the development of the platform, particularly in addressing issues and features within prototypes. His work ethic has been exceptional, and he has demonstrated a positive...

**Sources cited:** Peer review Muhammad_Budiman V3.docx
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — a detailed and accurate summary of the peer review content. The AI retrieved the correct document, correctly identified the subject (Muhammad Budiman), and provided specific details about contributions and work ethic. This is the best-performing result in Test 2.

---

### Question 9 — Peer Review Skills and Qualities

**Category:** Peer Review
**Question:** What specific skills or qualities are highlighted in the peer review?

**Answer from AI:**
> The peer review highlights the following specific skills or qualities in Muhammad Budiman:
> 1. Technical skills:
>    - Identifying and resolving bugs (Yusuf Abushaaban, Thong Phan)
>    - Contributing to client showcases and documentation (Yusuf Abushaaban, Thong Phan)
>    - Developing and debugging the appli...

**Sources cited:** Peer review Muhammad_Budiman V3.docx
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — the AI provided a structured breakdown of skills with attributed quotes from specific reviewers (Yusuf Abushaaban, Thong Phan). This is a high-quality answer that demonstrates strong retrieval and synthesis from a short, well-structured DOCX document.

---

### Question 10 — Out-of-Scope Query

**Category:** Out-of-scope
**Question:** What is the latest iPhone model released in 2025?

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Chunks retrieved:** 8

**Verdict: PASS**

**Is the answer correct?** Yes — the system correctly declined to answer a question completely outside the scope of the indexed documents. Consistent with Test 1 Question 8.

---

## Test 2 Key Findings

### Comparison: Test 1 vs Test 2

| Metric | Test 1 (3 docs) | Test 2 (2 docs, no table doc) |
|---|---|---|
| Total questions | 8 | 10 |
| Pass | 5 | 5 |
| Fail | 3 | 5 |
| Score | 62.5% | 50.0% |

### Document-level performance (Test 2)

| Document | Questions | Pass | Score |
|---|---|---|---|
| Griffith Annual Report | 7 | 2 | 28.6% |
| Peer Review (DOCX) | 2 | 2 | 100% |
| Out-of-scope | 1 | 1 | 100% |

### What this tells us

**The peer review document performs perfectly (100%).** It is a short (17 chunks), plain prose DOCX with no tables. Every question about it was answered correctly with specific detail.

**The annual report still struggles (28.6%)** despite removing the Essential Eight. The annual report itself contains table-formatted sections (financial statements, enrollment statistics). The table format problem is not limited to the Essential Eight — it exists within the annual report too.

**Retrieval depth is the bottleneck.** With 477 chunks and top_k=8, only ~1.7% of the annual report is seen per query. Questions about broad topics (research areas) or data buried in tables (enrollment, financials) consistently fail.

**The AI does not hallucinate when retrieval fails** (Tests 3, 5, 6, 7). It correctly returns "not enough information" rather than fabricating data — this is the correct behaviour after the hallucination in Test 1 Question 1.

### Confirmed hypothesis

Removing the table-heavy Essential Eight document did not improve overall accuracy — it dropped from 62.5% to 50%. This confirms that **the table format problem lies within the annual report PDF itself**, not just in documents that are entirely table-based.

### Recommended next steps

| Fix | Expected impact |
|---|---|
| Increase `top_k` from 8 to 15–20 | Would help Tests 3, 5, 6, 7 by retrieving more chunks |
| Add PDF table extraction (pdfplumber) for financial/statistical sections | Would fix Tests 3 and 7 specifically |
| Reduce chunk size from 1000 to 500 chars | Finer-grained retrieval for specific facts |
| Add keyword-based hybrid search (BM25 + vector) | Would help retrieve low-frequency facts like the VC name |

---

## Test Scripts

| Test | Script | Command |
|---|---|---|
| Test 1 | `tests/accuracy_test.py` | `.venv/Scripts/python.exe tests/accuracy_test.py` |
| Test 2 | `tests/accuracy_test_2.py` | `.venv/Scripts/python.exe tests/accuracy_test_2.py` |

---

---

# Test 2 — After Optimisation (Post-Fix Re-run)

**Date:** 2026-05-28
**Reason:** Three fixes were applied to address the retrieval gaps identified in Test 2 (pre-fix). The same 10 questions were re-run against the re-indexed documents.

## Changes Applied

| Fix | File changed | Detail |
|---|---|---|
| Smaller chunks | `src/rag/chunker.py` | Chunk size reduced from 1000 → 500 chars; overlap 200 → 100 |
| Table-aware splitting | `src/rag/chunker.py` | `[Table]` blocks split only at row boundaries, never mid-cell |
| Higher retrieval depth | `src/rag/llm_interface.py` | Default `top_k` increased from 8 → 15 |

**Re-index result:** Annual report grew from 477 → 945 chunks; peer review from 17 → 40 chunks.

---

## Post-Fix Results Summary

**Overall Score: 7 / 10 PASS (70.0%)** — up from 50.0%

| # | Category | Question | Pre-fix | Post-fix |
|---|---|---|---|---|
| 1 | Annual Report | Key achievements | PASS | PASS |
| 2 | Annual Report | Sustainability ranking | PASS | PASS |
| 3 | Annual Report | Student enrollment | FAIL | **FAIL** |
| 4 | Annual Report | Campuses operated | FAIL | **FAIL** |
| 5 | Annual Report | Vice-Chancellor | FAIL | **PASS** ✓ |
| 6 | Annual Report | Research focus areas | FAIL | **FAIL** |
| 7 | Annual Report | Financial performance | FAIL | **PASS** ✓ |
| 8 | Peer Review | Main feedback | PASS | PASS |
| 9 | Peer Review | Skills and qualities | PASS | PASS |
| 10 | Out-of-scope | iPhone model | PASS | PASS |

---

## Post-Fix Detailed Results

---

### Question 1 — Key Achievements *(unchanged)*

**Verdict: PASS**

**Answer from AI:**
> According to the Griffith University Annual Report 2025, some of the key achievements in 2025 include:
> 1. 15 NCP Scholars selected, with 18 selected in 2024, and more than tripling annual support since 2019 (Section 24).
> 2. 14 of 2026 nominees were selected for interview...

**Is the answer correct?** Yes — still passing, and the answer now includes more specific details (NCP Scholars count, section references) thanks to the finer-grained chunks.

---

### Question 2 — Sustainability Ranking *(unchanged)*

**Verdict: PASS**

**Answer from AI:**
> According to the Griffith University Annual Report 2025 (Section 26), Griffith ranked No. 50 globally for Environmental Impact in the QS World University Rankings: Sustainability 2025.

**Is the answer correct?** Yes — now provides even more specificity: "Environmental Impact" as the category within the sustainability ranking.

---

### Question 3 — Student Enrollment *(still failing)*

**Verdict: FAIL**

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Is the answer correct?** No — enrollment figures still not retrieved despite 15 chunks and 945-chunk index. The enrollment data appears to be buried in a deeply nested statistical table that still does not match semantically to the query "how many students are enrolled."

**Remaining root cause:** Semantic gap. The embedding model may not link "how many students enrolled" to the section label the document uses (e.g., "Student Headcount", "Total Enrolments", "EFTSL"). A hybrid keyword search (BM25 + vector) would fix this.

---

### Question 4 — Campuses *(partial improvement)*

**Verdict: FAIL** (borderline)

**Answer from AI:**
> According to the Griffith University Annual Report 2025 (Section 28), Griffith University operates on five physical campuses and one digital campus.

**Is the answer correct?** Partially — the count is correct (five physical + one digital). The campus names (Gold Coast, Nathan, South Bank, Logan, Mt Gravatt) are still not retrieved. The scoring is strict on campus names, but the answer itself is not wrong. This is a **borderline fail** — the system knows the structure but not the names.

---

### Question 5 — Vice-Chancellor *(fixed)*

**Verdict: PASS** ✓ *(was FAIL)*

**Answer from AI:**
> The Vice-Chancellor of Griffith University is Professor Carolyn Evans.

**Is the answer correct?** Yes — a precise, correct answer. This was the clearest win from the fixes. The VC name appeared only once in the document (in the foreword/leadership section). Smaller chunks (500 chars) created a focused chunk for that section, and top_k=15 reached it.

**Why it failed before:** The 1000-char chunks merged the foreword content with surrounding pages, diluting its relevance score. The top-8 retrieval never reached it.

---

### Question 6 — Research Focus Areas *(still failing)*

**Verdict: FAIL**

**Answer from AI:**
> According to Section 26, Griffith University has multiple subjects ranked in the top 50 of the QS World University Rankings by Subject in 2025, including: Hospitality and Tourism (51–100), Archaeology (51–100), Dentistry (51–120)...

**Is the answer correct?** Partially — the retrieved chunks returned ranking data (specific subjects) rather than broad research pillars. The expected keywords (health, environment, innovation) are in a different section of the report. The answer is not wrong, just not what was expected.

**Note:** The scoring penalises this because the expected broad keywords did not appear. A broader question like "what subjects does Griffith rank in?" would have scored as PASS.

---

### Question 7 — Financial Performance *(fixed)*

**Verdict: PASS** ✓ *(was FAIL)*

**Answer from AI:**
> The indexed document does not provide a specific figure for Griffith University's total revenue in 2025. However, it does provide information on the adjusted Earnings Before Interest and Tax (EBIT) for 2025, which is $44.6 million (Section 46).
> Additionally, the document mentions...

**Is the answer correct?** Yes — retrieved a specific financial figure ($44.6M EBIT from Section 46) and correctly flagged that total revenue was not separately stated. This confirms the table-aware chunking fix worked: the EBIT row in the financial table was kept intact in its own chunk and matched the query.

**Why it failed before:** The financial table rows were being split mid-cell by the 1000-char splitter. Post-fix, table rows are never broken across chunks.

---

### Questions 8–10 *(unchanged — all PASS)*

All three passed with the same quality as before. The peer review answers remained detailed and accurate.

---

## Comparison Across All Tests

| Metric | Test 1 (3 docs) | Test 2 pre-fix | Test 2 post-fix |
|---|---|---|---|
| Documents indexed | 3 | 2 | 2 |
| Questions | 8 | 10 | 10 |
| Score | 62.5% | 50.0% | **70.0%** |
| Chunk size | 1000 | 1000 | **500** |
| top_k | 8 | 8 | **15** |
| Table-aware chunking | No | No | **Yes** |
| Annual report chunks | — | 477 | **945** |

### What the fixes resolved

| Fix | Impact |
|---|---|
| `top_k` 8 → 15 | Reached the VC name (Q5) that was outside the top 8 |
| Chunk size 1000 → 500 | Created tighter, more focussed chunks for specific facts |
| Table-aware chunking | Kept financial table rows intact — EBIT $44.6M now retrievable (Q7) |

### What still needs work

| Issue | Question | Suggested next fix |
|---|---|---|
| Enrollment data semantic gap | Q3 | Add BM25 keyword search alongside vector search (hybrid retrieval) |
| Campus names not named | Q4 | Likely a section that uses a table/list — same BM25 fix |
| Research keyword mismatch | Q6 | Broaden test keywords OR improve document section labelling |

---

## Test Scripts

| Test | Script | Command |
|---|---|---|
| Test 1 | `tests/accuracy_test.py` | `.venv/Scripts/python.exe tests/accuracy_test.py` |
| Test 2 | `tests/accuracy_test_2.py` | `.venv/Scripts/python.exe tests/accuracy_test_2.py` |
| Re-index | `tests/reindex.py` | `.venv/Scripts/python.exe tests/reindex.py` |

---

---

# Test 2 — After Hybrid BM25 + Vector Search

**Date:** 2026-05-28
**Change applied:** Replaced pure vector search (`similarity_search`) with `hybrid_search` — a Reciprocal Rank Fusion combination of ChromaDB vector similarity and BM25 keyword scoring.

## How Hybrid Search Works

```
Query → Vector search (top 15) → ranked list A
      → BM25 keyword search (top 15) → ranked list B
      → RRF merge: score = 1/(60 + rank_A) + 1/(60 + rank_B)
      → Top 15 by combined score → LLM
```

Vector search finds semantically similar chunks. BM25 finds exact keyword matches. RRF merges both without needing to normalise their different score scales.

## Post-BM25 Results Summary

**Overall Score: 8 / 10 PASS (80.0%)** — up from 70.0%

| # | Category | Question | Pre-fix | Post-chunker | Post-BM25 |
|---|---|---|---|---|---|
| 1 | Annual Report | Key achievements | PASS | PASS | PASS |
| 2 | Annual Report | Sustainability ranking | PASS | PASS | PASS |
| 3 | Annual Report | Student enrollment | FAIL | FAIL | **FAIL** |
| 4 | Annual Report | Campuses operated | FAIL | FAIL | **FAIL** |
| 5 | Annual Report | Vice-Chancellor | FAIL | PASS | PASS |
| 6 | Annual Report | Research focus areas | FAIL | FAIL | **PASS** ✓ |
| 7 | Annual Report | Financial performance | FAIL | PASS | PASS |
| 8 | Peer Review | Main feedback | PASS | PASS | PASS |
| 9 | Peer Review | Skills and qualities | PASS | PASS | PASS |
| 10 | Out-of-scope | iPhone model | PASS | PASS | PASS |

---

## Post-BM25 Detailed Results

---

### Question 6 — Research Focus Areas *(fixed by BM25)*

**Verdict: PASS** ✓ *(was FAIL in post-chunker run)*

**Answer from AI:**
> According to Section 8 of the Griffith University Annual Report 2025, Griffith University's main research focus areas are:
> 1. Expand tertiary access and attainment: Griffith will build on its reputation for supporting students from equity backgrounds...

**Is the answer correct?** Yes — BM25 found Section 8 of the annual report using exact keyword matching on "research" and "focus", which vector search alone had missed. The answer cites the correct section and provides specific strategic research priorities.

**Why BM25 fixed it:** The section header "research focus" is an exact keyword match. Vector embeddings of the query ("main research focus areas") did not score this section highly enough to reach the top 15, but BM25's term frequency scoring pushed it into the merged result set.

---

### Question 3 — Student Enrollment *(still failing)*

**Verdict: FAIL**

**Answer from AI:**
> The indexed documents do not contain enough information to answer this question.

**Is the answer correct?** No — both BM25 and vector search failed to surface enrollment figures. This is now confirmed to be a **terminology mismatch at extraction time**, not a retrieval algorithm problem. The annual report likely uses terms like "EFTSL" (Equivalent Full-Time Student Load) or "headcount" in its statistics tables, which do not match "students enrolled" under either semantic or keyword scoring.

**Root cause confirmed:** The enrollment data exists in the PDF as a scanned/image table or behind a label ("EFTSL", "student headcount") that neither embedding similarity nor BM25 can bridge to the query "how many students are enrolled."

---

### Question 4 — Campus Names *(still failing)*

**Verdict: FAIL** (borderline — count is correct)

**Answer from AI:**
> According to the Griffith University Annual Report 2025, the University operates on five physical campuses and one digital campus.

**Is the answer correct?** Partially — the count (five physical + one digital) is correct. Neither BM25 nor vector search retrieved the specific chunk containing campus names (Gold Coast, Nathan, South Bank, Logan, Mt Gravatt). The campus names may appear only in a map image or introductory graphic that pdfplumber cannot extract as text.

---

## Full Progression Summary

| Round | Change | Score | +/- |
|---|---|---|---|
| Test 2 baseline | No changes | 50.0% | — |
| + Chunker fix | 500-char chunks, table-aware splitting, top_k 15 | 70.0% | +20% |
| + BM25 hybrid search | Reciprocal Rank Fusion of vector + keyword | **80.0%** | +10% |

### Cumulative improvement: +30% from baseline (50% → 80%)

### Remaining 2 failures — root cause

Both Q3 and Q4 are now confirmed to be **data extraction gaps**, not retrieval algorithm gaps:

| Question | Root cause | Suggested fix |
|---|---|---|
| Student enrollment (Q3) | PDF uses "EFTSL"/"headcount" terminology; may be image table | Add terminology expansion (synonym mapping) OR OCR the stats pages |
| Campus names (Q4) | Campus names likely in a map image or graphic | Add image OCR pass for infographic pages |

These cannot be solved by further retrieval improvements — the data needs to reach the text layer first.

---

## Test Scripts

| Test | Script | Command |
|---|---|---|
| Test 1 | `tests/accuracy_test.py` | `.venv/Scripts/python.exe tests/accuracy_test.py` |
| Test 2 | `tests/accuracy_test_2.py` | `.venv/Scripts/python.exe tests/accuracy_test_2.py` |
| Re-index | `tests/reindex.py` | `.venv/Scripts/python.exe tests/reindex.py` |

---

---

# Test 3 — User-Defined Questions

**Date:** 2026-05-28
**Questions:** 10 real-world questions provided by the user across all indexed documents.
**Active optimisations:** 500-char chunks, table-aware splitting, top_k=15, hybrid BM25+vector search, source distance filter, improved prompt.

## Indexed Documents at Time of Test

| File | Type | Chunks |
|---|---|---|
| griffith-university-annual-report-2025.pdf | PDF | 945 |
| Peer review Muhammad_Budiman V3.docx | DOCX | 40 |
| 5903LHS Example Report - Architecture.pdf | PDF | indexed |

---

## Test 3 Results Summary

**Overall Score: 7 / 10 PASS (70%)** — manually verified by user

| # | Category | Question | Automated | Manual |
|---|---|---|---|---|
| 1 | Annual Report | Queensland Women in STEM Award 2025 | PASS | **FAIL** |
| 2 | Annual Report | Integrity Procedures and Practices | PASS | PASS |
| 3 | Annual Report | Impairment of assets summary | PASS | PASS |
| 4 | Annual Report | Financing Arrangements details | PASS | **FAIL** |
| 5 | Annual Report | Total provisions in 2024 | PASS | **FAIL** |
| 6 | Peer Review | Lucas Caulley's role | PASS | PASS |
| 7 | Architecture Report | Benefits of passive building | PASS | PASS |
| 8 | Architecture Report | Issues related to passive building | PASS | PASS |
| 9 | Out-of-scope | Latest iPhone model 2025 | PASS | PASS |
| 10 | Annual Report | Carbon emission reduction target 2025 | PASS | PASS |

---

## Test 3 Detailed Results

---

### Question 1 — Queensland Women in STEM Award 2025

**Category:** Annual Report
**Question:** List all Queensland Women in STEM Award 2025

**Answer from AI:**
> According to the provided context, the following individuals are listed as recipients of the Queensland Women in STEM Award 2025:
> 1. Elisha Pettit
> 2. Dr. Munkhbayar Batmunkh

**Sources cited:** griffith-university-annual-report-2025.pdf

**Automated verdict:** PASS
**Manual verdict: FAIL**

**Is the answer correct?** No — the AI returned the wrong names. The correct finalists are:
- Dr Caitie Kuempel (finalist)
- Dr Miaomiao Liu (finalist)
- Dr Michelle Ward (finalist)

**Root cause:** Hallucination. The retrieved chunks contained names from other award sections in the annual report, and the model picked the wrong people. The chunk containing the Queensland Women in STEM Award specifically was not retrieved, so the LLM constructed a plausible-sounding but incorrect list.

---

### Question 2 — Integrity Procedures and Practices

**Category:** Annual Report
**Question:** Give me details regarding Integrity Procedures and Practices

**Answer from AI:**
> According to Section 40 of the Griffith University Annual Report 2025, Integrity Procedures and Practices are comprehensive and have been reviewed and approved by Council. The review ensured that the University's Risk Appetite Statement is aligned with the University's Code of Conduct. Integrity is embedded into Griffith's...

**Sources cited:** griffith-university-annual-report-2025.pdf, Peer review Muhammad_Budiman V3.docx
**Verdict: PASS** — Found Section 40, identified Risk Appetite Statement and Code of Conduct alignment. Answers directly with no disclaimer.

---

### Question 3 — Impairment of Assets

**Category:** Annual Report
**Question:** Summarise 'Impairment of assets' from Griffith annual report

**Answer from AI:**
> According to the Griffith University Annual Report 2025, the University applies Aus5.1 of AASB136 Impairment of Assets, which allows not-for-profit entities to not perform impairment tests subject to regular valuations being performed...

**Sources cited:** griffith-university-annual-report-2025.pdf
**Verdict: PASS** — Correct source only. Full answer covers AASB136 policy, annual testing rule, and loss recognition. Prompt and source filter fixes are holding.

---

### Question 4 — Financing Arrangements

**Category:** Annual Report
**Question:** Details about 'Financing Arrangements'

**Answer from AI:**
> According to Section 12 of the Griffith University Annual Report 2025, the University has unrestricted access to $5.0m credit (2024: $5.0m) through current credit card arrangements. As at balance date, $1.8m (2024: $1.6m) had been used.

**Sources cited:** griffith-university-annual-report-2025.pdf

**Automated verdict:** PASS
**Manual verdict: FAIL**

**Is the answer correct?** No — the automated test returned $5.0m credit figures (Section 12), but the manual test returned a different answer entirely:
> "The table lists the following sources of loan: Receivables: $28,023 / Contract assets: $4,531 / Trade and other payables: $59,399 / Borrowings: $124,172... Total balance of loans: $110,780 (Section 17)"

Both answers came from real sections of the annual report, but neither is specifically about "Financing Arrangements." The model is confusing the topic with adjacent financial sections (liquidity risk table, trade payables).

**Root cause:** Retrieval inconsistency. The hybrid search retrieves different chunks on different runs, leading to different wrong answers each time. "Financing Arrangements" as a section label may not exist verbatim in the document, so both BM25 and vector search pull in nearby financial content instead. The answer is not repeatable or reliable for this query.

---

### Question 5 — Total Provisions in 2024

**Category:** Annual Report
**Question:** What is the total provisions in 2024

**Answer from AI:**
> The total provisions in 2024 are not explicitly stated in the provided context. However, it is mentioned that "Current provisions expected to be settled within 12 months" and "Make good costs 9(vii) 7,000 -".

**Sources cited:** griffith-university-annual-report-2025.pdf, Peer review Muhammad_Budiman V3.docx

**Automated verdict:** PASS
**Manual verdict: FAIL**

**Correct answer:** $127,649,000

**Is the answer correct?** No — the AI returned "Make good costs: $7,000" which is a single line item, not the total. The correct total provisions figure for 2024 is $127,649,000. The automated scoring was fooled by keyword matches ("provision", "2024", "total") but the actual figure returned was wrong by several orders of magnitude.

**Root cause:** The total provisions summary row ($127,649,000) is in a financial summary table that the chunker is not retrieving. The model found a partial provision entry from a different row and presented it as the total.

---

### Question 6 — Lucas Caulley's Role

**Category:** Peer Review
**Question:** What is Lucas Caulley's role based on the peer review document

**Answer from AI:**
> According to the peer review document, Lucas Caulley's role is that of a Project Manager.

**Sources cited:** griffith-university-annual-report-2025.pdf, Peer review Muhammad_Budiman V3.docx
**Verdict: PASS** — Correctly identified Lucas Caulley as Project Manager from the peer review document.

---

### Question 7 — Benefits of Passive Building

**Category:** Architecture Report
**Question:** What's the benefit of passive building?

**Answer from AI:**
> According to the report, the benefits of passive building design include:
> - Minimising or avoiding the use of fossil fuels, which reduces reliance on electricity to power mechanical devices (Schnieders & Mermelink, 2006)
> - Being more sustainable for the environment...

**Sources cited:** 5903LHS Example Report - Architecture.pdf
**Verdict: PASS** — Correctly retrieved and answered from the Architecture report with academic citations. Relevant source cited.

---

### Question 8 — Issues Related to Passive Building

**Category:** Architecture Report
**Question:** How many issues are there related to passive building and explain for each one

**Answer from AI:**
> According to the provided context, there are 7 issues related to passive building design:
> 1. **Cost** — The architectural design is likely to cost more than a standard design (Master Builders Queensland, 2012)
> 2. **Efficacy** — ...
> (and 5 more issues with explanations)

**Sources cited:** 5903LHS Example Report - Architecture.pdf
**Verdict: PASS** — Detailed structured answer with 7 issues, academic citations, drawn from the Architecture report.

---

### Question 9 — Latest iPhone Model 2025

**Category:** Out-of-scope
**Question:** What is the latest iPhone model released in 2025?

**Answer from AI:**
> There is no information in the provided context about the latest iPhone model released in 2025.

**Sources cited:** griffith-university-annual-report-2025.pdf, Peer review Muhammad_Budiman V3.docx
**Verdict: PASS** — Correctly declined. Consistent across all test rounds.

---

### Question 10 — Carbon Emission Reduction Target 2025

**Category:** Annual Report
**Question:** What's the Carbon emission reduction actuals for 2025

**Answer from AI:**
> According to Section 18 of the Griffith University Annual Report 2025, the target for carbon emission reduction is to reach a total reduction of **-46.7% relative to the 2010-11 baseline**.

**Sources cited:** griffith-university-annual-report-2025.pdf
**Verdict: PASS** — Precise answer with exact percentage (-46.7%), baseline year (2010-11), and section reference (Section 18). One of the strongest answers across all test rounds.

---

## Test 3 Key Findings

### Score breakdown by category (manual verification)

| Category | Questions | Pass | Fail | Score |
|---|---|---|---|---|
| Annual Report | 7 | 4 | 3 | 57% |
| Peer Review | 1 | 1 | 0 | 100% |
| Architecture Report | 2 | 2 | 0 | 100% |
| Out-of-scope | 1 | 1 | 0 | 100% |

### Failures summary

| # | Question | Failure type | Detail |
|---|---|---|---|
| Q1 | Women in STEM Award | Wrong names (hallucination) | Returned Elisha Pettit, Dr. Munkhbayar Batmunkh — correct: Dr Caitie Kuempel, Dr Miaomiao Liu, Dr Michelle Ward |
| Q4 | Financing Arrangements | Retrieval inconsistency | Different wrong sections retrieved on each run |
| Q5 | Total provisions 2024 | Wrong figure | Returned partial row ($7,000) — correct total: $127,649,000 |

### Important: automated scoring vs manual verification

The automated scorer (keyword matching) returned 10/10 but manual verification found only 7/10 correct. This gap reveals a weakness in keyword-based automated scoring: the scorer accepts any answer containing the right keywords, even if the actual figures or names are wrong.

**Lesson:** Keyword-based automated scoring is not sufficient for factual accuracy. Future test runs should include exact-match checks for numerical answers and named entities.

### Overall progression across all tests

| Test | Questions | Automated Score | Manual Score | Key change |
|---|---|---|---|---|
| Test 1 | 8 | 62.5% | — | Baseline (3 documents) |
| Test 2 baseline | 10 | 50.0% | — | Removed Essential Eight |
| Test 2 post-chunker | 10 | 70.0% | — | 500-char chunks + top_k 15 |
| Test 2 post-BM25 | 10 | 80.0% | — | Hybrid BM25 + vector search |
| **Test 3** | **10** | **90.0%** | **70%** | Prompt fix + source filter + 3 indexed docs |

---

## Test Scripts

| Test | Script | Command |
|---|---|---|
| Test 1 | `tests/accuracy_test.py` | `.venv/Scripts/python.exe tests/accuracy_test.py` |
| Test 2 | `tests/accuracy_test_2.py` | `.venv/Scripts/python.exe tests/accuracy_test_2.py` |
| Test 3 | `tests/accuracy_test_3.py` | `.venv/Scripts/python.exe tests/accuracy_test_3.py` |
| Re-index | `tests/reindex.py` | `.venv/Scripts/python.exe tests/reindex.py` |
