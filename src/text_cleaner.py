import re


NOISE_PHRASES = [
    "table of contents",
    "for internal use only",
    "final report",
    "moss adams llp",
    "city of cupertino",
    "enterprise risk assessment report",
    "risk assessment employee survey results",
    "table of contents – continued",
    "table of contents - continued",
]

TABLE_LIKE_PHRASES = [
    "moderate-to-high",
    "low-to-moderate",
    "risk category",
    "risk level",
    "likelihood",
    "preparedness",
    "trajectory",
    "flat",
    "increasing",
    "decreasing",
]


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def is_mostly_numeric(line: str) -> bool:
    stripped = re.sub(r"\s+", "", line)
    if not stripped:
        return False

    digit_count = sum(ch.isdigit() for ch in stripped)
    return digit_count / len(stripped) > 0.35


def is_all_caps_short(line: str) -> bool:
    words = line.split()
    if not words:
        return False

    letters_only = re.sub(r"[^A-Za-z]", "", line)
    if not letters_only:
        return False

    return line.upper() == line and len(words) <= 12


def looks_like_toc_entry(line: str) -> bool:
    lowered = line.lower().strip()

    if re.search(r"\b\d+\s*$", lowered) and len(lowered.split()) <= 10:
        return True

    if re.search(r"\.{2,}", lowered):
        return True

    if re.match(r"^[a-z]\.\s", lowered) and re.search(r"\b\d+\s*$", lowered):
        return True

    return False


def looks_like_address_or_contact(line: str) -> bool:
    lowered = line.lower()

    address_markers = [
        "avenue", "street", "suite", "seattle", "wa", "phone", "fax"
    ]

    marker_hits = sum(1 for marker in address_markers if marker in lowered)
    digit_count = sum(ch.isdigit() for ch in line)

    return marker_hits >= 1 and digit_count >= 3


def looks_like_table_matrix(line: str) -> bool:
    lowered = line.lower()

    hits = sum(1 for phrase in TABLE_LIKE_PHRASES if phrase in lowered)

    if hits >= 3:
        return True

    if "moderate-to-high" in lowered and "low-to-moderate" in lowered:
        return True

    if len(line.split()) > 18 and hits >= 2:
        return True

    return False


def is_noisy_line(line: str) -> bool:
    stripped = line.strip()
    lowered = stripped.lower()

    if not stripped:
        return True

    if len(stripped) < 4:
        return True

    if re.fullmatch(r"\d+", stripped):
        return True

    if re.fullmatch(r"page\s+\d+", lowered):
        return True

    if is_mostly_numeric(stripped):
        return True

    if is_all_caps_short(stripped):
        return True

    if looks_like_toc_entry(stripped):
        return True

    if looks_like_address_or_contact(stripped):
        return True

    if looks_like_table_matrix(stripped):
        return True

    for phrase in NOISE_PHRASES:
        if phrase in lowered:
            return True

    return False


def merge_broken_lines(lines: list[str]) -> list[str]:
    merged = []
    buffer = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if not buffer:
            buffer = line
            continue

        # if the previous buffer hasn't ended the sentence, continue joining
        if not re.search(r"[.!?:]$", buffer):
            if len(line.split()) <= 3:
                buffer += " " + line
            elif line[:1].islower():
                buffer += " " + line
            else:
                merged.append(buffer.strip())
                buffer = line
        else:
            merged.append(buffer.strip())
            buffer = line

    if buffer:
        merged.append(buffer.strip())

    return merged


def clean_extracted_text(text: str) -> str:
    if not text or not text.strip():
        return ""

    text = normalize_whitespace(text)
    raw_lines = text.split("\n")

    cleaned_lines = []
    for line in raw_lines:
        stripped = line.strip()

        if is_noisy_line(stripped):
            continue

        # skip lines with only 1-2 words (likely noise)
        if len(stripped.split()) <= 2:
            continue

        # skip lines with repeated noise characters
        if re.search(r"[•◆■]{2,}", stripped):
            continue

        cleaned_lines.append(stripped)

    merged_lines = merge_broken_lines(cleaned_lines)

    cleaned_text = "\n".join(merged_lines)
    cleaned_text = re.sub(r"\n{2,}", "\n", cleaned_text).strip()

    return cleaned_text