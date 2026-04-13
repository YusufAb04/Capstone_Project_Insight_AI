from pathlib import Path
from collections import defaultdict, Counter
import shutil
import re
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import streamlit as st
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_community.vectorstores import Chroma

DEFAULT_DOCS_DIR = "docs"
CHROMA_DIR = "chroma_db"
CHAT_MODEL = "llama3.2:3b"
EMBED_MODEL = "nomic-embed-text"
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".csv", ".xlsx"}

DEFAULT_EXCLUDED_FILE_NAMES = [
    "secret.txt",
    "private.docx",
    "confidential.pdf",
    "license.txt",
    "thirdpartynotices.txt",
]

DEFAULT_EXCLUDED_FOLDER_NAMES = [
    "private",
    "protected",
    "do_not_scan",
    "venv",
    "lib",
    "site-packages",
    "dist-info",
    "__pycache__",
    ".git",
    "node_modules",
    "build",
    "dist",
]

DEFAULT_EXCLUDED_KEYWORDS = [
    "password",
    "bank account",
    "tax file number",
]

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "using", "used",
    "are", "was", "were", "has", "have", "had", "will", "shall", "can", "could",
    "would", "should", "all", "any", "not", "but", "our", "their", "your", "you",
    "its", "out", "about", "over", "under", "more", "most", "such", "than", "then",
    "into", "also", "only", "very", "much", "many", "some", "each", "other", "these",
    "those", "they", "them", "their", "there", "here", "where", "when", "what", "which",
    "who", "whom", "been", "being", "through", "within", "without", "across", "between",
    "local", "document", "documents", "file", "files", "data", "system", "assistant",
    "project", "prototype", "analysis", "processing", "device", "folder", "source",
    "sources", "page", "pages", "section", "sections"
}

RISK_RULES = {
    "Operational Risk": [
        "delay", "delayed", "overdue", "missed deadline", "bottleneck",
        "resource shortage", "communication gap", "handover issue", "backlog",
        "manual process", "outage", "inefficiency", "dependency"
    ],
    "Financial Risk": [
        "overspend", "over budget", "budget overrun", "cost increase",
        "deficit", "revenue decline", "cash flow", "financial pressure",
        "expense", "budget", "funding shortfall", "cost"
    ],
    "Security Risk": [
        "password", "breach", "unauthorized", "malware", "vulnerability",
        "attack", "cybersecurity", "security weakness", "access control",
        "incident", "threat", "exposure", "phishing"
    ],
    "Privacy / Compliance Risk": [
        "privacy", "personal data", "confidential", "compliance",
        "regulation", "retention policy", "audit", "sensitive information",
        "governance", "policy gap", "non-compliance"
    ],
    "Supply Chain Risk": [
        "vendor", "supplier", "third-party", "outsourcing",
        "dependency", "procurement", "external provider", "service provider"
    ]
}

ACTION_RULES = {
    "Operational Risk": [
        "Review delivery timelines, escalation paths, and cross-team coordination processes.",
        "Assign clearer ownership for operational bottlenecks and track remediation milestones."
    ],
    "Financial Risk": [
        "Conduct a budget variance review and tighten cost-control checkpoints.",
        "Introduce recurring financial monitoring for high-cost activities or subscriptions."
    ],
    "Security Risk": [
        "Review security controls and strengthen vulnerability management practices.",
        "Improve access control, monitoring, and incident response readiness."
    ],
    "Privacy / Compliance Risk": [
        "Perform a compliance review for sensitive information handling and retention obligations.",
        "Update governance, audit, and privacy procedures where controls appear weak or unclear."
    ],
    "Supply Chain Risk": [
        "Assess third-party dependencies and strengthen vendor oversight.",
        "Review procurement and supplier-management controls for concentration risk."
    ]
}

OPPORTUNITY_RULES = {
    "Security Risk": "Strengthen the organisation's security posture by formalising control reviews and remediation planning.",
    "Privacy / Compliance Risk": "Improve assurance and regulatory readiness through clearer governance and audit alignment.",
    "Supply Chain Risk": "Increase resilience by improving vendor oversight and third-party risk visibility.",
    "Operational Risk": "Improve service delivery by addressing process bottlenecks and strengthening coordination.",
    "Financial Risk": "Create better budget discipline and cost visibility through recurring financial review cycles."
}

FINDING_RULES = {
    "Operational Risk": "The document suggests operational execution may depend on stronger coordination, ownership, or process consistency.",
    "Financial Risk": "The text contains signals that cost control, budget monitoring, or funding discipline may need attention.",
    "Security Risk": "The content points to security-control, vulnerability, or access-management considerations that may require review.",
    "Privacy / Compliance Risk": "The document references compliance, privacy, or audit-related concepts that imply governance obligations.",
    "Supply Chain Risk": "The text indicates possible dependence on vendors, procurement processes, or third-party services."
}

DOC_TYPE_RULES = {
    "Policy / Framework": ["policy", "framework", "governance", "standard", "control", "compliance"],
    "Meeting Notes": ["meeting", "minutes", "attendees", "agenda", "action items", "discussion"],
    "Budget / Financial": ["budget", "cost", "expense", "revenue", "forecast", "financial"],
    "Security / Technical": ["security", "cybersecurity", "vulnerability", "system", "network", "access control"],
    "Internal Memo / Review": ["review", "internal", "note", "concern", "issue", "follow-up"],
}

RISK_PROMPT_TEMPLATE = """
You are an internal business intelligence and risk analysis assistant.

Analyze the provided document and produce a structured report with the following numbered sections:
1. Potential Risks
2. Opportunities & Strategic Value
3. Key Findings
4. Recommended Management Actions

Important instructions:
- Infer likely risks when the document is framework-based, policy-based, or strategic.
- Do not say "no risks found" too quickly.
- If explicit risks are not listed, identify implied risks such as governance gaps, compliance weaknesses, operational inefficiencies, privacy weaknesses, cyber exposure, or supply chain dependence.
- Keep the output concise, specific, business-oriented, and suitable for managers.
- Prefer practical statements over generic statements.
- Only use the provided text.

Document text:
{document_text}
"""

QA_PROMPT_TEMPLATE = """
You are an offline AI assistant for confidential documents.

Answer the user's question using ONLY the context below.
If the answer is not clearly supported by the context, say:
"I could not find a reliable answer in the provided documents."

Format your response exactly as:
Answer: <2-4 concise sentences>
Evidence:
- <source file>: <very short evidence statement>
- <source file>: <very short evidence statement>

Do not invent facts. Mention source file names.

Context:
{context}

Question:
{question}
"""

EXEC_SUMMARY_PROMPT = """
You are an internal executive-summary assistant.

Using only the provided text, write a concise executive summary with these sections:
1. Top Risks
2. Key Insights
3. Priority Actions

Keep it practical, management-oriented, and brief.

Text:
{document_text}
"""


def init_state():
    if "docs_dir" not in st.session_state:
        st.session_state.docs_dir = DEFAULT_DOCS_DIR
    if "excluded_file_names" not in st.session_state:
        st.session_state.excluded_file_names = DEFAULT_EXCLUDED_FILE_NAMES.copy()
    if "excluded_folder_names" not in st.session_state:
        st.session_state.excluded_folder_names = DEFAULT_EXCLUDED_FOLDER_NAMES.copy()
    if "excluded_keywords" not in st.session_state:
        st.session_state.excluded_keywords = DEFAULT_EXCLUDED_KEYWORDS.copy()


def normalize_lines(text: str) -> List[str]:
    return [line.strip().lower() for line in text.splitlines() if line.strip()]


def contains_excluded_keyword(text: str, excluded_keywords: List[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in excluded_keywords)


def should_skip_file(file_path: Path, excluded_files: List[str], excluded_folders: List[str], excluded_keywords: List[str]) -> Tuple[bool, str]:
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return True, "Unsupported file type"
    path_parts = {part.lower() for part in file_path.parts}
    if path_parts & {folder.lower() for folder in excluded_folders}:
        return True, "Excluded folder"
    if file_path.name.lower() in {name.lower() for name in excluded_files}:
        return True, "Excluded file name"
    file_path_lower = str(file_path).lower()
    if any(keyword.lower() in file_path_lower for keyword in excluded_keywords):
        return True, "Excluded keyword in path"
    return False, ""


def load_file(file_path: Path):
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return PyMuPDFLoader(str(file_path)).load()
    if suffix in {".txt", ".csv"}:
        return TextLoader(str(file_path), encoding="utf-8").load()
    if suffix == ".docx":
        return Docx2txtLoader(str(file_path)).load()
    if suffix == ".xlsx":
        raise ValueError(".xlsx loading is not implemented in this prototype yet")
    return []


def load_documents(docs_dir, excluded_file_names, excluded_folder_names, excluded_keywords):
    docs = []
    skipped_files = []
    docs_path = Path(docs_dir)
    if not docs_path.exists() or not docs_path.is_dir():
        return docs, skipped_files
    for file_path in docs_path.rglob("*"):
        if not file_path.is_file():
            continue
        should_skip, reason = should_skip_file(file_path, excluded_file_names, excluded_folder_names, excluded_keywords)
        if should_skip:
            skipped_files.append((str(file_path), reason))
            continue
        try:
            loaded_docs = load_file(file_path)
            if not loaded_docs:
                skipped_files.append((str(file_path), "No content loaded"))
                continue
            combined_text = "\n".join(doc.page_content for doc in loaded_docs if doc.page_content)
            if contains_excluded_keyword(combined_text, excluded_keywords):
                skipped_files.append((str(file_path), "Excluded keyword found in content"))
                continue
            docs.extend(loaded_docs)
        except Exception as e:
            skipped_files.append((str(file_path), f"Error loading file: {e}"))
    return docs, skipped_files


@st.cache_resource
def build_vectorstore(docs_dir, excluded_file_names_tuple, excluded_folder_names_tuple, excluded_keywords_tuple):
    documents, skipped_files = load_documents(
        docs_dir,
        list(excluded_file_names_tuple),
        list(excluded_folder_names_tuple),
        list(excluded_keywords_tuple),
    )
    if not documents:
        return None, None, [], skipped_files
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_documents(documents)
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
    )
    source_files = sorted({doc.metadata.get("source", "unknown") for doc in documents})
    return vectorstore, documents, source_files, skipped_files


def source_label(doc) -> str:
    source = doc.metadata.get("source", "unknown")
    return Path(source).name if source else "unknown"


def short_snippet(text: str, length: int = 180) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:length] + ("..." if len(text) > length else "")


def render_source_cards(results):
    st.subheader("Supporting Evidence")
    seen = set()
    for i, doc in enumerate(results, start=1):
        source = source_label(doc)
        snippet = short_snippet(doc.page_content, 260)
        key = (source, snippet)
        if key in seen:
            continue
        seen.add(key)
        with st.expander(f"Evidence {i}: {source}"):
            st.write(snippet)
            st.caption(str(doc.metadata))


def render_skipped_files(skipped_files):
    st.subheader("Skipped / Excluded Files")
    if not skipped_files:
        st.success("No files were excluded.")
        return
    for file_path, reason in skipped_files:
        with st.expander(f"{file_path}"):
            st.write(f"Reason: {reason}")


def reset_index():
    if Path(CHROMA_DIR).exists():
        shutil.rmtree(CHROMA_DIR, ignore_errors=True)
    st.cache_resource.clear()


def tokenize_text(text: str):
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-_]{2,}", text.lower())
    return [token for token in tokens if token not in STOPWORDS and not token.isdigit()]


def extract_keywords_from_text(text: str, top_n=15):
    return Counter(tokenize_text(text)).most_common(top_n)


def extract_keywords_for_collection(documents, top_n=15):
    return extract_keywords_from_text("\n\n".join(doc.page_content for doc in documents if doc.page_content), top_n=top_n)


def extract_keywords_for_file(documents, selected_file, top_n=15):
    file_text = "\n\n".join(
        doc.page_content for doc in documents
        if doc.metadata.get("source", "unknown") == selected_file and doc.page_content
    )
    return extract_keywords_from_text(file_text, top_n=top_n)


def render_keyword_chart(keyword_data, title):
    if not keyword_data:
        st.warning("No keywords found.")
        return
    words = [item[0] for item in keyword_data]
    counts = [item[1] for item in keyword_data]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(words, counts)
    ax.set_title(title)
    ax.set_xlabel("Keyword")
    ax.set_ylabel("Frequency")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    st.pyplot(fig)


def detect_risks_from_text(text: str) -> Dict[str, List[str]]:
    text_lower = text.lower()
    detected = {}
    for category, keywords in RISK_RULES.items():
        matches = [kw for kw in keywords if kw in text_lower]
        if matches:
            detected[category] = matches
    return detected


def classify_document_type(text: str, file_name: str = "") -> str:
    combined = f"{file_name} {text[:2500]}".lower()
    scores = {}
    for doc_type, keywords in DOC_TYPE_RULES.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score:
            scores[doc_type] = score
    if not scores:
        return "General Business Document"
    return max(scores, key=scores.get)


def extract_section(text: str, heading: str) -> str:
    if not text:
        return ""
    pattern = rf"(?im)^\s*{re.escape(heading)}\s*$\n?(.*?)(?=^\s*\d+\.\s+[A-Z][^\n]*$|\Z)"
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def clean_llm_section(text: str) -> List[str]:
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = []
    bad_exact = {
        "none", "n/a", "no major findings extracted.", "no findings extracted.",
        "no major opportunities extracted.", "no major actions extracted.",
        "**", "*", ":", ":*", ":**", "-", "--", "---", "•", "#", "##", "###",
    }
    for line in lines:
        line = re.sub(r"^[-*•]\s*", "", line)
        line = re.sub(r"^\d+\.\s*", "", line)
        line = re.sub(r"^\*+\s*", "", line)
        line = re.sub(r"\s*\*+$", "", line)
        line = line.strip(" :-\t")
        if not line:
            continue
        if line.lower() in bad_exact:
            continue
        if re.fullmatch(r"[*:#\-.]+", line):
            continue
        if re.match(r"^\d+\.\s+[A-Z]", line):
            continue
        cleaned.append(line)
    return cleaned


def build_rule_based_risk_lines(detected_risks: Dict[str, List[str]]) -> List[str]:
    if not detected_risks:
        return [
            "No strong explicit risk indicators were detected from keyword analysis.",
            "The document may be more descriptive, strategic, or policy-focused than incident-focused.",
        ]
    lines = []
    for category, matches in detected_risks.items():
        pretty_matches = ", ".join(matches[:5])
        lines.append(f"**{category}:** indicators found from terms such as {pretty_matches}, suggesting this area may require management attention.")
    return lines


def build_opportunity_lines(detected_risks: Dict[str, List[str]], llm_output: str) -> List[str]:
    llm_lines = clean_llm_section(extract_section(llm_output, "2. Opportunities & Strategic Value"))
    if llm_lines:
        return llm_lines
    lines = [OPPORTUNITY_RULES[category] for category in detected_risks if category in OPPORTUNITY_RULES]
    if not lines:
        lines.append("The document can support stronger internal visibility by surfacing governance, control, or decision-support themes for management review.")
    return list(dict.fromkeys(lines))[:4]


def build_finding_lines(detected_risks: Dict[str, List[str]], llm_output: str) -> List[str]:
    llm_lines = clean_llm_section(extract_section(llm_output, "3. Key Findings"))
    if not llm_lines:
        llm_lines = clean_llm_section(extract_section(llm_output, "3. Key Insights"))
    if llm_lines:
        return llm_lines
    lines = [FINDING_RULES[category] for category in detected_risks if category in FINDING_RULES]
    if not lines:
        lines.append("The document appears primarily descriptive, with limited direct evidence of incidents but useful signals for governance or planning review.")
    return list(dict.fromkeys(lines))[:4]


def build_action_lines(detected_risks: Dict[str, List[str]], llm_output: str) -> List[str]:
    llm_lines = clean_llm_section(extract_section(llm_output, "4. Recommended Management Actions"))
    if not llm_lines:
        llm_lines = clean_llm_section(extract_section(llm_output, "4. Recommended Actions"))
    if llm_lines:
        return llm_lines
    lines = []
    for category in detected_risks:
        lines.extend(ACTION_RULES.get(category, []))
    if not lines:
        lines.append("Review the document with relevant stakeholders and confirm whether additional control, governance, or operational follow-up is required.")
    return list(dict.fromkeys(lines))[:6]


def estimate_confidence(detected_risks: Dict[str, List[str]], llm_output: str) -> str:
    count = len(detected_risks)
    opp = clean_llm_section(extract_section(llm_output, "2. Opportunities & Strategic Value"))
    find = clean_llm_section(extract_section(llm_output, "3. Key Findings")) or clean_llm_section(extract_section(llm_output, "3. Key Insights"))
    act = clean_llm_section(extract_section(llm_output, "4. Recommended Management Actions")) or clean_llm_section(extract_section(llm_output, "4. Recommended Actions"))
    real_llm_support = bool(opp or find or act)
    if count >= 3 and real_llm_support:
        return "High confidence. Multiple risk categories and supporting management-oriented signals were detected."
    if count >= 1:
        return "Medium confidence. Results are based on extracted text and rule-assisted interpretation."
    return "Low to medium confidence. The document appears more descriptive than issue-focused, so inferred insights may be limited."


def calculate_risk_score(detected_risks: Dict[str, List[str]]) -> Tuple[str, str]:
    count = len(detected_risks)
    matched = {m for matches in detected_risks.values() for m in matches}
    severe_terms = {"breach", "malware", "unauthorized", "phishing", "vulnerability", "deficit", "funding shortfall"}
    if count >= 4 or matched & severe_terms:
        return "High", "Multiple categories or high-severity indicators were detected."
    if count >= 2:
        return "Medium", "More than one risk category was detected in the analysed content."
    if count == 1:
        return "Low", "A limited number of risk signals were detected."
    return "Low", "The content appears more descriptive than incident-heavy."


def collect_evidence_snippets(text: str, detected_risks: Dict[str, List[str]], max_items: int = 5) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    evidence = []
    for category, keywords in detected_risks.items():
        for sentence in sentences:
            sentence_clean = re.sub(r"\s+", " ", sentence).strip()
            if not sentence_clean:
                continue
            lowered = sentence_clean.lower()
            if any(kw in lowered for kw in keywords):
                evidence.append(f"**{category}:** {short_snippet(sentence_clean, 220)}")
                break
        if len(evidence) >= max_items:
            break
    return evidence


def build_risk_report(file_name: str, file_text: str, llm_output: str, detected_risks: Dict[str, List[str]], doc_type: str) -> str:
    risk_lines = build_rule_based_risk_lines(detected_risks)
    opportunity_lines = build_opportunity_lines(detected_risks, llm_output)
    finding_lines = build_finding_lines(detected_risks, llm_output)
    action_lines = build_action_lines(detected_risks, llm_output)
    confidence_text = estimate_confidence(detected_risks, llm_output)
    risk_score, risk_score_reason = calculate_risk_score(detected_risks)
    evidence_lines = collect_evidence_snippets(file_text, detected_risks)

    lines = [f"## Risk & Management Insight Report - {file_name}", ""]
    lines.append("### 1. Document Type")
    lines.append(f"- {doc_type}")
    lines.append("")
    lines.append("### 2. Overall Risk Score")
    lines.append(f"- **{risk_score}**")
    lines.append(f"- {risk_score_reason}")
    lines.append("")
    lines.append("### 3. Potential Risks")
    lines.extend([f"- {line}" for line in risk_lines])
    lines.append("")
    lines.append("### 4. Opportunities & Strategic Value")
    lines.extend([f"- {line}" for line in opportunity_lines])
    lines.append("")
    lines.append("### 5. Key Findings")
    lines.extend([f"- {line}" for line in finding_lines])
    lines.append("")
    lines.append("### 6. Recommended Management Actions")
    lines.extend([f"- {line}" for line in action_lines])
    lines.append("")
    lines.append("### 7. Supporting Evidence")
    if evidence_lines:
        lines.extend([f"- {line}" for line in evidence_lines])
    else:
        lines.append("- No short evidence snippets were extracted from the available text.")
    lines.append("")
    lines.append("### 8. Confidence Level")
    lines.append(f"- {confidence_text}")
    lines.append("")
    lines.append("### 9. Source Document")
    lines.append(f"- {file_name}")
    return "\n".join(lines)


def build_context(results) -> str:
    return "\n\n".join(
        f"Source: {source_label(doc)}\nContent: {doc.page_content}"
        for doc in results
    )


def parse_qa_answer(raw_answer: str, results) -> Tuple[str, List[str]]:
    answer_text = raw_answer.strip()
    evidence_lines = []
    match = re.search(r"Answer:\s*(.*?)(?:\n\s*Evidence:|\Z)", raw_answer, flags=re.DOTALL | re.IGNORECASE)
    if match:
        answer_text = match.group(1).strip()
    evidence_match = re.search(r"Evidence:\s*(.*)", raw_answer, flags=re.DOTALL | re.IGNORECASE)
    if evidence_match:
        evidence_lines = [line.strip(" -") for line in evidence_match.group(1).splitlines() if line.strip()]
    if not evidence_lines:
        evidence_lines = [f"{source_label(doc)}: {short_snippet(doc.page_content, 120)}" for doc in results[:3]]
    return answer_text, evidence_lines[:4]


def ask_question(vectorstore, question):
    llm = OllamaLLM(model=CHAT_MODEL)
    results = vectorstore.similarity_search(question, k=5)
    context = build_context(results)
    answer = llm.invoke(QA_PROMPT_TEMPLATE.format(context=context, question=question))
    parsed_answer, evidence_lines = parse_qa_answer(answer, results)
    return parsed_answer, evidence_lines, results


def summarise_all_documents(documents):
    llm = OllamaLLM(model=CHAT_MODEL)
    combined_text = "\n\n".join(
        f"Source: {source_label(doc)}\nContent: {doc.page_content}"
        for doc in documents
    )[:7000]
    prompt = f"""
You are an offline AI assistant for confidential documents.

Summarise the following document collection.
Focus on:
- main topics
- important details
- key projects, people, or themes if present

Use only the provided text.
Keep the summary clear and structured in bullet points.

Text:
{combined_text}
"""
    return llm.invoke(prompt)


def summarise_one_file(documents, selected_file):
    llm = OllamaLLM(model=CHAT_MODEL)
    grouped_docs = defaultdict(list)
    for doc in documents:
        grouped_docs[doc.metadata.get("source", "unknown")].append(doc.page_content)
    file_text = "\n\n".join(grouped_docs[selected_file])[:7000]
    prompt = f"""
You are an offline AI assistant for confidential documents.

Summarise this document clearly.
Focus on:
- purpose of the document
- key information
- important details
- notable projects, education, skills, or facts if relevant

Use only the provided text.
Return a concise structured summary.

Document source:
{Path(selected_file).name}

Document text:
{file_text}
"""
    return llm.invoke(prompt)


def generate_collection_risk_report(documents):
    llm = OllamaLLM(model=CHAT_MODEL)
    combined_text = "\n\n".join(
        f"Source: {source_label(doc)}\nContent: {doc.page_content}"
        for doc in documents
    )[:7000]
    detected_risks = detect_risks_from_text(combined_text)
    llm_output = llm.invoke(RISK_PROMPT_TEMPLATE.format(document_text=combined_text))
    doc_type = classify_document_type(combined_text, "collection")
    return build_risk_report("Collection", combined_text, llm_output, detected_risks, doc_type)


def generate_file_risk_report(documents, selected_file):
    llm = OllamaLLM(model=CHAT_MODEL)
    file_text = "\n\n".join(
        doc.page_content for doc in documents
        if doc.metadata.get("source", "unknown") == selected_file and doc.page_content
    )[:7000]
    detected_risks = detect_risks_from_text(file_text)
    llm_output = llm.invoke(RISK_PROMPT_TEMPLATE.format(document_text=file_text))
    doc_type = classify_document_type(file_text, selected_file)
    return build_risk_report(Path(selected_file).name, file_text, llm_output, detected_risks, doc_type)


def generate_executive_summary(documents):
    llm = OllamaLLM(model=CHAT_MODEL)
    combined_text = "\n\n".join(
        f"Source: {source_label(doc)}\nContent: {doc.page_content}"
        for doc in documents
    )[:7000]
    return llm.invoke(EXEC_SUMMARY_PROMPT.format(document_text=combined_text))


def generate_cross_document_insights(documents, source_files):
    file_text_map = {}
    for source in source_files:
        file_text_map[source] = "\n\n".join(
            doc.page_content for doc in documents if doc.metadata.get("source", "unknown") == source and doc.page_content
        )[:5000]

    per_file_risks = {source: detect_risks_from_text(text) for source, text in file_text_map.items()}
    category_to_files = defaultdict(list)
    type_counts = Counter()
    for source, risks in per_file_risks.items():
        doc_type = classify_document_type(file_text_map[source], source)
        type_counts[doc_type] += 1
        for category in risks:
            category_to_files[category].append(Path(source).name)

    lines = ["## Cross-Document Insights", ""]
    lines.append("### Repeated Risk Themes")
    if category_to_files:
        for category, files in sorted(category_to_files.items(), key=lambda x: len(x[1]), reverse=True):
            unique_files = list(dict.fromkeys(files))
            lines.append(f"- **{category}:** appears across {len(unique_files)} file(s) — {', '.join(unique_files[:5])}.")
    else:
        lines.append("- No repeated risk themes were strongly detected across the loaded files.")

    lines.append("")
    lines.append("### Document Type Mix")
    if type_counts:
        for doc_type, count in type_counts.most_common():
            lines.append(f"- **{doc_type}:** {count} file(s)")
    else:
        lines.append("- No document types were confidently classified.")

    lines.append("")
    lines.append("### Management Interpretation")
    if category_to_files:
        top_categories = [c for c, _ in sorted(category_to_files.items(), key=lambda x: len(x[1]), reverse=True)[:3]]
        lines.append(f"- The strongest recurring themes are {', '.join(top_categories)}.")
        lines.append("- These repeated signals may warrant portfolio-level review rather than isolated document-by-document analysis.")
    else:
        lines.append("- The current collection appears mixed or descriptive, with limited recurring risk patterns.")

    return "\n".join(lines)


def main():
    st.set_page_config(page_title="INSIGHT.AI Prototype V11", layout="wide")
    init_state()

    st.title("INSIGHT.AI Prototype V11")
    st.caption("Secure local document intelligence for internal business, operational, and risk analysis.")

    st.sidebar.header("System Info")
    st.sidebar.write(f"Chat Model: `{CHAT_MODEL}`")
    st.sidebar.write(f"Embedding Model: `{EMBED_MODEL}`")

    st.sidebar.header("Document Source")
    docs_dir_input = st.sidebar.text_input("Documents folder path", value=st.session_state.docs_dir, help="Example: docs or D:\\CompanyFiles")

    folder_col1, folder_col2 = st.sidebar.columns(2)
    with folder_col1:
        if st.button("Apply Folder", use_container_width=True):
            st.session_state.docs_dir = docs_dir_input.strip()
            reset_index()
            st.rerun()
    with folder_col2:
        if st.button("Use Default", use_container_width=True):
            st.session_state.docs_dir = DEFAULT_DOCS_DIR
            reset_index()
            st.rerun()

    current_docs_path = Path(st.session_state.docs_dir)
    st.sidebar.write(f"Current folder: `{current_docs_path}`")
    if current_docs_path.exists() and current_docs_path.is_dir():
        st.sidebar.success("Folder found")
    else:
        st.sidebar.error("Folder not found")

    st.sidebar.header("Rule Settings")
    excluded_files_text = st.sidebar.text_area("Excluded file names (one per line)", value="\n".join(st.session_state.excluded_file_names), height=120)
    excluded_folders_text = st.sidebar.text_area("Excluded folder names (one per line)", value="\n".join(st.session_state.excluded_folder_names), height=140)
    excluded_keywords_text = st.sidebar.text_area("Excluded keywords (one per line)", value="\n".join(st.session_state.excluded_keywords), height=140)

    rule_col1, rule_col2 = st.sidebar.columns(2)
    with rule_col1:
        if st.button("Apply Rules", use_container_width=True):
            st.session_state.excluded_file_names = normalize_lines(excluded_files_text)
            st.session_state.excluded_folder_names = normalize_lines(excluded_folders_text)
            st.session_state.excluded_keywords = normalize_lines(excluded_keywords_text)
            reset_index()
            st.rerun()
    with rule_col2:
        if st.button("Reset Defaults", use_container_width=True):
            st.session_state.excluded_file_names = DEFAULT_EXCLUDED_FILE_NAMES.copy()
            st.session_state.excluded_folder_names = DEFAULT_EXCLUDED_FOLDER_NAMES.copy()
            st.session_state.excluded_keywords = DEFAULT_EXCLUDED_KEYWORDS.copy()
            reset_index()
            st.rerun()

    vectorstore, documents, source_files, skipped_files = build_vectorstore(
        st.session_state.docs_dir,
        tuple(st.session_state.excluded_file_names),
        tuple(st.session_state.excluded_folder_names),
        tuple(st.session_state.excluded_keywords),
    )

    if not documents or vectorstore is None:
        st.error("No allowed documents found in the selected folder. Please adjust the folder path, rules, or files.")
        render_skipped_files(skipped_files)
        return

    st.sidebar.success(f"Loaded {len(documents)} document page(s)/section(s)")
    st.sidebar.info(f"Indexed {len(source_files)} source file(s)")
    st.sidebar.warning(f"Skipped {len(skipped_files)} file(s)")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Ask Questions",
        "Executive Summary",
        "Portfolio Summary",
        "Single Document Summary",
        "Keyword & Topic Extraction",
        "Risk & Management Insight Report",
        "Cross-Document Insights",
        "Security & Exclusion Report",
    ])

    with tab1:
        st.subheader("Ask Questions")
        question = st.text_input("Enter your question")
        if st.button("Get Answer", use_container_width=True):
            if question.strip():
                with st.spinner("Generating answer..."):
                    answer, evidence_lines, results = ask_question(vectorstore, question)
                st.subheader("Answer")
                st.write(answer)
                st.subheader("Supporting Evidence")
                for line in evidence_lines:
                    st.write(f"- {line}")
                render_source_cards(results)
            else:
                st.warning("Please enter a question.")

    with tab2:
        st.subheader("Executive Summary")
        if st.button("Generate Executive Summary", use_container_width=True):
            with st.spinner("Generating executive summary..."):
                summary = generate_executive_summary(documents)
            st.markdown(summary)

    with tab3:
        st.subheader("Portfolio Summary")
        if st.button("Generate Portfolio Summary", use_container_width=True):
            with st.spinner("Generating summary..."):
                summary = summarise_all_documents(documents)
            st.write(summary)

    with tab4:
        st.subheader("Single Document Summary")
        selected_file = st.selectbox("Choose a file", source_files)
        if st.button("Generate File Summary", use_container_width=True):
            with st.spinner("Generating file summary..."):
                summary = summarise_one_file(documents, selected_file)
            st.write(summary)
            file_text = "\n\n".join(doc.page_content for doc in documents if doc.metadata.get("source", "unknown") == selected_file and doc.page_content)
            st.caption(f"Detected document type: {classify_document_type(file_text, selected_file)}")

    with tab5:
        st.subheader("Keyword & Topic Extraction")
        keyword_mode = st.radio("Choose extraction scope", ["Collection", "Single File"], horizontal=True)
        top_n = st.slider("Number of keywords", min_value=5, max_value=30, value=10, step=1)
        if keyword_mode == "Collection":
            if st.button("Extract Collection Keywords", use_container_width=True):
                keyword_data = extract_keywords_for_collection(documents, top_n=top_n)
                st.subheader("Top Collection Keywords")
                if keyword_data:
                    for word, count in keyword_data:
                        st.write(f"- **{word}**: {count}")
                else:
                    st.write("No keywords found.")
                render_keyword_chart(keyword_data, "Top Collection Keywords")
        else:
            selected_keyword_file = st.selectbox("Choose file for keyword extraction", source_files, key="keyword_file_select")
            if st.button("Extract File Keywords", use_container_width=True):
                keyword_data = extract_keywords_for_file(documents, selected_keyword_file, top_n=top_n)
                st.subheader(f"Top Keywords for {Path(selected_keyword_file).name}")
                if keyword_data:
                    for word, count in keyword_data:
                        st.write(f"- **{word}**: {count}")
                else:
                    st.write("No keywords found.")
                render_keyword_chart(keyword_data, f"Top Keywords - {Path(selected_keyword_file).name}")

    with tab6:
        st.subheader("Risk & Management Insight Report")
        report_mode = st.radio("Choose reporting scope", ["Collection", "Single File"], horizontal=True, key="risk_mode")
        if report_mode == "Collection":
            if st.button("Generate Collection Risk & Insight Report", use_container_width=True):
                with st.spinner("Generating report..."):
                    report = generate_collection_risk_report(documents)
                st.markdown(report)
        else:
            selected_report_file = st.selectbox("Choose file for report generation", source_files, key="risk_file_select")
            if st.button("Generate File Risk & Insight Report", use_container_width=True):
                with st.spinner("Generating report..."):
                    report = generate_file_risk_report(documents, selected_report_file)
                st.markdown(report)

    with tab7:
        st.subheader("Cross-Document Insights")
        if st.button("Generate Cross-Document Insights", use_container_width=True):
            with st.spinner("Analysing cross-document patterns..."):
                insights = generate_cross_document_insights(documents, source_files)
            st.markdown(insights)

    with tab8:
        render_skipped_files(skipped_files)


if __name__ == "__main__":
    main()
