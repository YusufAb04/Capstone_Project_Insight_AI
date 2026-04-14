
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime


def parse_json_field(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []


def build_export_text_from_records(records: list[dict]) -> str:
    total_files = len(records)
    avg_risk = sum(r.get("risk_score") or 0 for r in records) / total_files if total_files else 0
    risk_counts = Counter((r.get("risk_label") or "Unknown") for r in records)
    type_counts = Counter((r.get("document_type") or "Unknown") for r in records)

    lines = []
    lines.append("INSIGHT.AI BUSINESS EDITION — EXECUTIVE REPORT")
    lines.append("=" * 60)
    lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Indexed files: {total_files}")
    lines.append(f"Average risk score: {avg_risk:.1f}")
    lines.append("")

    lines.append("RISK DISTRIBUTION")
    for label, count in risk_counts.items():
        lines.append(f"- {label}: {count}")

    lines.append("")
    lines.append("DOCUMENT TYPE DISTRIBUTION")
    for label, count in type_counts.items():
        lines.append(f"- {label}: {count}")

    lines.append("")
    lines.append("TOP HIGH-RISK FILES")
    high = sorted(records, key=lambda x: (x.get("risk_score") or 0), reverse=True)[:10]
    for rec in high:
        lines.append(f"- {rec.get('file_name')} | {rec.get('risk_label')} ({rec.get('risk_score') or 0})")
        lines.append(f"  Type: {rec.get('document_type') or 'Unknown'}")
        lines.append(f"  Takeaway: {rec.get('management_takeaway') or 'No takeaway available.'}")

    lines.append("")
    lines.append("DETAILED FILE SUMMARY")
    for rec in records[:100]:
        lines.append(f"- File: {rec.get('file_name')}")
        lines.append(f"  Path: {rec.get('file_path')}")
        lines.append(f"  Risk: {rec.get('risk_label')} ({rec.get('risk_score') or 0})")
        lines.append(f"  OCR Used: {'Yes' if rec.get('ocr_used') else 'No'}")
        lines.append(f"  Summary: {rec.get('summary') or 'No summary available.'}")
    return "\n".join(lines)


def build_export_json_from_records(records: list[dict]) -> str:
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "record_count": len(records),
        "records": records,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
