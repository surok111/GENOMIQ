"""Parse HL7 v2 ORU^R01 laboratory messages into gene/result dicts.

Looks at OBX segments:
  OBX-3  observation identifier  (CYP2C19, CYP2C19*2, rs4244285, ...)
  OBX-5  observation value       (*1/*2, CT, TT, ...)

Returns the same list-of-dicts shape as parse_patient_report /
parse_raw_lab_report: {"gene", "result", "comment"}.
"""

from __future__ import annotations

import re

from raw_parser import (
    RSID_TO_GENE,
    _NEGATIVE,
    _is_gene_symbol,
    _put,
    _result_from_text_value,
)

# MSH|^~\&  — standard HL7 v2 header (field sep |, encoding ^~\&)
_MSH_MARKERS = ("MSH|^~\\&", "MSH|^~\\\\&")
_GENE_TOKEN = re.compile(r"([A-Za-z][A-Za-z0-9]+)(?:\*\d+)?")
_RSID = re.compile(r"(rs\d+)", re.IGNORECASE)


def looks_like_hl7(text: str, path: str | None = None) -> bool:
    """True for .hl7/.oru files or text that contains an MSH|^~\\& header."""
    if path and str(path).lower().endswith((".hl7", ".oru")):
        return True
    if not text:
        return False
    head = text[:5000]
    return any(marker in head for marker in _MSH_MARKERS)


def parse_hl7_report(text: str) -> list[dict[str, str]]:
    """Extract gene/result pairs from OBX segments of an HL7 v2 message."""
    try:
        if not text or not str(text).strip():
            return []
        by_gene: dict[str, dict[str, str]] = {}
        for segment in _segments(text):
            if not segment.startswith("OBX|"):
                continue
            fields = segment.split("|")
            if len(fields) < 6:
                continue
            ident = fields[3].strip()
            value = fields[5].strip()
            gene = _gene_from_obx3(ident)
            if not gene:
                continue
            if not value or _NEGATIVE.search(value):
                continue
            result = _normalize_obx5(value)
            if not result:
                continue
            _put(by_gene, gene, result, f"HL7 OBX-3={ident}")
        return list(by_gene.values())
    except Exception:
        return []


def _segments(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def _gene_from_obx3(obx3: str) -> str | None:
    """Gene symbol from OBX-3 (CWE components separated by ^)."""
    for part in obx3.split("^"):
        part = part.strip()
        if not part:
            continue
        m = _RSID.search(part)
        if m:
            mapped = RSID_TO_GENE.get(m.group(1).lower())
            if mapped:
                return mapped
        m = _GENE_TOKEN.search(part)
        if m:
            token = m.group(1).upper()
            if _is_gene_symbol(token):
                return token
    return None


def _normalize_obx5(value: str) -> str | None:
    # CWE value: *1/*2^Intermediate metabolizer^L  → first component
    primary = value.split("^", 1)[0].strip()
    return _result_from_text_value(primary) or (primary[:80] if primary else None)
