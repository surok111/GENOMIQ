"""Parse mixed laboratory exports (VCF rows + karyotype + free-text notes).

Returns the same list-of-dicts shape as interpreter.parse_patient_report:
    {"gene": str, "result": str, "comment": str}

Only rsIDs that map to genes in the GenomIQ knowledge base are kept
from strict VCF rows. Log lines and GENE: genotype summaries may add
extra symbols (e.g. VKORC1). Negative findings are dropped.
The old Ген/Результат parser is unchanged.
"""

from __future__ import annotations

import re
from typing import Any

RSID_TO_GENE: dict[str, str] = {
    "rs4244285": "CYP2C19",
    "rs4986893": "CYP2C19",
    "rs12248560": "CYP2C19",
    "rs1801133": "MTHFR",
    "rs1801131": "MTHFR",
    "rs6025": "F5",
    "rs1799963": "F2",
    "rs429358": "APOE",
    "rs7412": "APOE",
    "rs1800566": "NQO1",
    "rs4149056": "SLCO1B1",
    "rs1799853": "CYP2C9",
    "rs1057910": "CYP2C9",
    "rs9923231": "VKORC1",
}

# Used when a log line has GT but the VCF dump omitted FORMAT/SAMPLE.
RSID_REF_ALT: dict[str, tuple[str, str]] = {
    "rs4244285": ("G", "A"),
    "rs4986893": ("G", "A"),
    "rs12248560": ("C", "T"),
    "rs1801133": ("C", "T"),
    "rs1801131": ("A", "C"),
    "rs6025": ("C", "T"),
    "rs429358": ("T", "C"),
    "rs7412": ("C", "T"),
    "rs1800566": ("C", "T"),
    "rs4149056": ("T", "C"),
    "rs1799853": ("C", "T"),
    "rs1057910": ("A", "C"),
    "rs9923231": ("C", "T"),
}

CYP2C19_STAR: dict[str, str] = {
    "rs4244285": "*2",
    "rs4986893": "*3",
    "rs12248560": "*17",
}

CYP2C9_STAR: dict[str, str] = {
    "rs1799853": "*2",
    "rs1057910": "*3",
}

EXTRA_GENES = {"VKORC1", "BRCA1", "BRCA2", "F2", "F5", "APOE", "MTHFR"}

# CHROM POS ID REF ALT QUAL FILTER INFO FORMAT SAMPLE  (tabs or spaces)
_VCF_ROW = re.compile(
    r"^(?:chr)?\S+\s+\d+\s+(rs\d+)\s+([ACGTN]+)\s+([ACGTN.,]+)\s+\S+\s+\S+\s+\S+\s+(\S+)\s+(\S+)",
    re.IGNORECASE,
)
# Truncated VCF (no FORMAT/SAMPLE / no GT).
_VCF_LOOSE = re.compile(
    r"^(?:chr)?\S+\s+\d+\s+(rs\d+)\s+([ACGTN]+)\s+([ACGTN.,]+)\b",
    re.IGNORECASE,
)
_LOG_GT = re.compile(
    r"(rs\d+)\W+(?:Gene:\s*)?([A-Z][A-Z0-9]+)\b.*?GT:\s*(\./\.|[0-9][/|][0-9])",
    re.IGNORECASE,
)
_TEXT_GENE = re.compile(
    r"(?m)^(?:[-*•]\s*)?([A-Z][A-Z0-9]{1,14})\s*:\s*(.+?)\s*$",
)
_INLINE_GENE_RESULT = re.compile(
    r"(?:Gene|Ген)\s*:\s*([A-Za-z0-9]+)\s*[;,]\s*(?:Result|Результат)\s*:\s*([^;\n]+)",
    re.IGNORECASE,
)
_CLASSIC_GENE = re.compile(
    r"^(?:Gene|Ген)\s*:\s*([A-Za-z0-9]+)\s*$",
    re.IGNORECASE,
)
_CLASSIC_RESULT = re.compile(
    r"^(?:Result|Результат)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
_RSID_ASSIGN = re.compile(
    r"(rs\d+)\s*=\s*([A-Za-z0-9/*]+)\s*(?:\(([A-Za-z0-9]+)\))?",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"не\s+обнаруж|не\s+выявл|\bnegative\b|not\s+detected|wild\s*type",
    re.IGNORECASE,
)
_KARYOTYPE = re.compile(
    r"Result:\s*(\d{2},(?:XX|XY)(?:,[^\s\[]+)?)",
    re.IGNORECASE,
)
_CYP2C19_NOTE = re.compile(
    r"CYP2C19.*?\*(\d+).*?(heterozygous|homozygous)",
    re.IGNORECASE,
)
_APOE_NOTE = re.compile(
    r"APOE\s+genotype\s+is\s+(E[234]\s*/\s*E[234])",
    re.IGNORECASE,
)
_MTHFR_NOTE = re.compile(
    r"MTHFR\s+C677T\s+(homozygous|heterozygous)\s*\((\w+)\)",
    re.IGNORECASE,
)
_SLCO_NOTE = re.compile(
    r"SLCO1B1.*?c\.521T>C\s+(heterozygous|homozygous)",
    re.IGNORECASE,
)


def looks_like_raw_lab(text: str, path: str | None = None) -> bool:
    """True for .vcf files or mixed lab dumps that embed a VCF header.

    Scans the first 5000 characters (not only the first line) so a dump
    that starts with garbage still matches ``##fileformat=VCF`` or ``#CHROM``.
    """
    if path and str(path).lower().endswith(".vcf"):
        return True
    if not text:
        return False
    head = text[:5000]
    low = head.lower()
    if "##fileformat=vcf" in low or "#chrom" in low:
        return True
    return (
        "[VCF_HEADER]" in head
        or "[KARYOTYPE_REPORT]" in head
        or "[RAW_VCF_DUMP_START]" in head
        or "[INTERPRETATION_LOG]" in head
        or "[TEXT_SUMMARY]" in head
        or "found variant rs" in low
    )


def parse_raw_lab_report(text: str) -> list[dict[str, str]]:
    """Extract gene/result pairs from a mixed VCF + karyotype + notes file."""
    try:
        if not text or not str(text).strip():
            return []
        by_gene: dict[str, dict[str, str]] = {}
        vcf_hits, ref_alt = _parse_vcf(text)
        log_hits = _parse_log_gt(text, ref_alt)
        _merge_vcf(by_gene, _dedupe_hits(vcf_hits + log_hits))
        _merge_notes(by_gene, text)
        _merge_classic_pairs(by_gene, text)
        _merge_rsid_assign(by_gene, text)
        _merge_text_summary(by_gene, text)
        _merge_karyotype(by_gene, text)
        return list(by_gene.values())
    except Exception:
        return []


def _parse_vcf(text: str) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
    hits: list[dict[str, Any]] = []
    ref_alt: dict[str, tuple[str, str]] = dict(RSID_REF_ALT)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m_full = _VCF_ROW.match(line)
        if m_full:
            rsid, ref, alt, fmt, sample = m_full.groups()
            rsid_key = rsid.lower()
            if rsid_key in RSID_TO_GENE:
                ref_alt[rsid_key] = (ref.upper(), alt.split(",")[0].upper())
            gene = RSID_TO_GENE.get(rsid_key)
            if gene is None:
                continue
            alleles = _alleles_from_gt(ref, alt, fmt, sample)
            if alleles is None:
                continue
            gt_code, pair = alleles
            hits.append(_hit(gene, rsid_key, ref, alt, gt_code, pair))
            continue
        m_loose = _VCF_LOOSE.match(line)
        if not m_loose:
            continue
        rsid, ref, alt = m_loose.group(1).lower(), m_loose.group(2).upper(), m_loose.group(3).upper()
        if rsid in RSID_TO_GENE:
            ref_alt[rsid] = (ref, alt.split(",")[0])
    return hits, ref_alt


def _parse_log_gt(
    text: str, ref_alt: dict[str, tuple[str, str]]
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for raw in text.splitlines():
        if "GT:" not in raw:
            continue
        m = _LOG_GT.search(raw)
        if not m:
            continue
        rsid, gene, gt = m.group(1).lower(), m.group(2).upper(), m.group(3)
        if "." in gt:
            continue  # missing GT (./.)
        if not _is_gene_symbol(gene):
            gene = RSID_TO_GENE.get(rsid, "")
        if not gene:
            continue
        ref, alt = ref_alt.get(rsid, ("", ""))
        alleles = _alleles_from_gt(ref, alt, "GT", gt) if ref and alt else None
        pair = alleles[1] if alleles else gt.replace("|", "/")
        gt_code = alleles[0] if alleles else gt.replace("|", "/")
        hits.append(_hit(gene, rsid, ref or "N", alt or "N", gt_code, pair))
    return hits


def _hit(gene: str, rsid: str, ref: str, alt: str, gt: str, pair: str) -> dict[str, Any]:
    return {
        "gene": gene,
        "rsid": rsid,
        "ref": ref.upper(),
        "alt": alt.split(",")[0].upper(),
        "gt": gt,
        "pair": pair,
    }


def _dedupe_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per (gene, rsid); prefer a real REF/ALT allele pair."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for hit in hits:
        key = (hit["gene"], hit["rsid"])
        prev = best.get(key)
        if prev is None or _hit_rank(hit) >= _hit_rank(prev):
            best[key] = hit
    return list(best.values())


def _hit_rank(hit: dict[str, Any]) -> int:
    pair = hit.get("pair", "").replace("/", "")
    if re.fullmatch(r"[ACGT]{2}", pair, re.I):
        return 2
    return 1


def _alleles_from_gt(
    ref: str, alt: str, fmt: str, sample: str
) -> tuple[str, str] | None:
    keys = fmt.split(":")
    vals = sample.split(":")
    try:
        gt_raw = vals[keys.index("GT")]
    except (ValueError, IndexError):
        gt_raw = vals[0] if vals else ""
    tokens = re.split(r"[|/]", gt_raw)
    if len(tokens) < 2:
        return None
    if any(tok in {".", ""} for tok in tokens[:2]):
        return None  # missing GT (./.)
    try:
        idxs = [int(tok) for tok in tokens[:2]]
    except ValueError:
        return None
    alt_alleles = [a.upper() for a in alt.split(",") if a and a != "."]
    # Unphase 0|1 → 0/1. Multi-allelic 1/2 (or index past ALT) → het 0/1.
    if any(i > 1 for i in idxs) or any(i > len(alt_alleles) for i in idxs):
        if not ref or not alt_alleles:
            return None
        idxs = [0, 1]
    gt_code = f"{idxs[0]}/{idxs[1]}"
    letters: list[str] = []
    for idx in idxs:
        if idx == 0:
            letters.append(ref.upper())
        elif 1 <= idx <= len(alt_alleles):
            letters.append(alt_alleles[idx - 1])
        else:
            return None
    return gt_code, f"{letters[0]}/{letters[1]}"


def _merge_vcf(by_gene: dict[str, dict[str, str]], hits: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        grouped.setdefault(hit["gene"], []).append(hit)

    for gene, rows in grouped.items():
        if gene == "CYP2C19":
            result, comment = _star_from_vcf(rows, CYP2C19_STAR)
        elif gene == "CYP2C9":
            result, comment = _star_from_vcf(rows, CYP2C9_STAR)
        elif gene == "APOE":
            result, comment = _apoe_from_vcf(rows)
        else:
            row = rows[0]
            compact = row["pair"].replace("/", "")
            result = compact
            comment = f"{row['rsid']} {row['ref']}>{row['alt']} GT={row['gt']} → {row['pair']}"
        _put(by_gene, gene, result, comment)


def _star_from_vcf(rows: list[dict[str, Any]], star_map: dict[str, str]) -> tuple[str, str]:
    stars: list[str] = []
    bits: list[str] = []
    for row in rows:
        bits.append(f"{row['rsid']} {row['pair']} (GT={row['gt']})")
        star = star_map.get(row["rsid"])
        if not star:
            continue
        a, b = row["gt"].replace("|", "/").split("/")[:2]
        called = (a != "0") + (b != "0")
        stars.extend([star] * called)
    if not stars:
        result = "*1/*1"
    elif len(stars) == 1:
        result = f"*1/{stars[0]}"
    else:
        result = f"{stars[0]}/{stars[1]}"
    return result, "; ".join(bits)


def _apoe_from_vcf(rows: list[dict[str, Any]]) -> tuple[str, str]:
    rs429358 = next((r for r in rows if r["rsid"] == "rs429358"), None)
    rs7412 = next((r for r in rows if r["rsid"] == "rs7412"), None)
    bits = [f"{r['rsid']} {r['pair']} (GT={r['gt']})" for r in rows]
    isoform = _apoe_isoform(
        rs429358["gt"] if rs429358 else None,
        rs7412["gt"] if rs7412 else None,
    )
    result = isoform or (rows[0]["pair"].replace("/", "") if rows else "")
    return result, "; ".join(bits)


def _apoe_isoform(gt_429358: str | None, gt_7412: str | None) -> str | None:
    """Unphased ε2/ε3/ε4 from rs429358 (T→C) and rs7412 (C→T)."""
    if not gt_429358 or not gt_7412:
        return None
    c4 = _alt_count(gt_429358)  # C alleles at rs429358 → ε4
    c2 = _alt_count(gt_7412)  # T alleles at rs7412 → ε2
    if c4 + c2 > 2:
        return None
    c3 = 2 - c4 - c2
    alleles = ["E2"] * c2 + ["E3"] * c3 + ["E4"] * c4
    return f"{alleles[0]}/{alleles[1]}"


def _alt_count(gt: str) -> int:
    a, b = gt.replace("|", "/").split("/")[:2]
    return int(a != "0") + int(b != "0")


def _merge_classic_pairs(by_gene: dict[str, dict[str, str]], text: str) -> None:
    """Gene: X ; Result: Y  and two-line Ген: / Результат: (single-line values)."""
    pending: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("=") or line.startswith("-"):
            pending = None
            continue
        m_inline = _INLINE_GENE_RESULT.search(line)
        if m_inline:
            gene = m_inline.group(1).upper()
            result = _result_from_text_value(m_inline.group(2).strip())
            if _is_gene_symbol(gene) and result and not _NEGATIVE.search(result):
                _put(by_gene, gene, result, "from Gene/Result")
            pending = None
            continue
        m_gene = _CLASSIC_GENE.match(line)
        if m_gene:
            pending = m_gene.group(1).upper()
            continue
        m_res = _CLASSIC_RESULT.match(line)
        if m_res and pending:
            result = _result_from_text_value(m_res.group(1).strip())
            if _is_gene_symbol(pending) and result and not _NEGATIVE.search(m_res.group(1)):
                _put(by_gene, pending, result, "from Ген/Результат")
            pending = None


def _merge_rsid_assign(by_gene: dict[str, dict[str, str]], text: str) -> None:
    """rs1800566=CT (NQO1) style assignments."""
    for m in _RSID_ASSIGN.finditer(text):
        rsid = m.group(1).lower()
        value = m.group(2).strip()
        paren = (m.group(3) or "").upper()
        gene = paren if _is_gene_symbol(paren) else RSID_TO_GENE.get(rsid, "")
        if not gene:
            continue
        result = _result_from_text_value(value) or value.replace("/", "").upper()
        if result and not _NEGATIVE.search(result):
            _put(by_gene, gene, result, f"{rsid}={value}")


def _merge_notes(by_gene: dict[str, dict[str, str]], text: str) -> None:
    m = _CYP2C19_NOTE.search(text)
    if m:
        star, zyg = m.group(1), m.group(2).lower()
        result = f"*1/*{star}" if zyg.startswith("het") else f"*{star}/*{star}"
        _put(by_gene, "CYP2C19", result, "from RAW_NOTES")

    m = _APOE_NOTE.search(text)
    if m:
        result = re.sub(r"\s+", "", m.group(1).upper())
        _put(by_gene, "APOE", result, "from RAW_NOTES")

    m = _MTHFR_NOTE.search(text)
    if m:
        result = m.group(2).upper()
        _put(by_gene, "MTHFR", result, f"C677T {m.group(1).lower()} (RAW_NOTES)")

    m = _SLCO_NOTE.search(text)
    if m:
        result = "TC" if m.group(1).lower().startswith("het") else "CC"
        _put(by_gene, "SLCO1B1", result, "c.521T>C (RAW_NOTES)")


def _merge_text_summary(by_gene: dict[str, dict[str, str]], text: str) -> None:
    for m in _TEXT_GENE.finditer(text):
        gene = m.group(1).upper()
        raw_val = m.group(2).strip()
        if not _is_gene_symbol(gene):
            continue
        if _NEGATIVE.search(raw_val):
            by_gene.pop(gene, None)
            continue
        result = _result_from_text_value(raw_val)
        if not result:
            continue
        _put(by_gene, gene, result, "from TEXT_SUMMARY")


def _result_from_text_value(value: str) -> str | None:
    value = re.split(r"\s*->\s*", value, maxsplit=1)[0].strip()
    m = re.search(r"(\*\d+\s*/\s*\*\d+)", value)
    if m:
        return re.sub(r"\s+", "", m.group(1))
    m = re.search(r"\b(E[234]\s*/\s*E[234])\b", value, re.I)
    if m:
        return re.sub(r"\s+", "", m.group(1).upper())
    m = re.search(r"\b([ACGT])\s*/\s*([ACGT])\b", value, re.I)
    if m:
        return f"{m.group(1)}{m.group(2)}".upper()
    m = re.search(r"\b([ACGT]{2})\b", value, re.I)
    if m:
        return m.group(1).upper()
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:80] if cleaned else None


def _merge_karyotype(by_gene: dict[str, dict[str, str]], text: str) -> None:
    m = _KARYOTYPE.search(text)
    if not m:
        return
    iscn = m.group(1).rstrip(",")
    _put(by_gene, "KARYOTYPE", iscn, "ISCN from KARYOTYPE_REPORT")


def _is_gene_symbol(name: str) -> bool:
    n = name.upper()
    if n in EXTRA_GENES or n in RSID_TO_GENE.values():
        return True
    return bool(re.fullmatch(r"[A-Z]{2,}\d+[A-Z0-9]*", n))


def _clarity(result: str) -> int:
    r = result.strip()
    if not r:
        return 0
    if re.search(r"\*\d+/\*\d+", r):
        return 3
    if re.fullmatch(r"E[234]/E[234]", r, re.I):
        return 3
    compact = r.replace("/", "").replace(" ", "")
    if re.fullmatch(r"[ACGT]{2}", compact, re.I):
        return 2
    return 1


def _put(by_gene: dict[str, dict[str, str]], gene: str, result: str, note: str) -> None:
    if not result or _NEGATIVE.search(result):
        return
    if gene not in by_gene:
        by_gene[gene] = {"gene": gene, "result": result, "comment": note}
        return
    prev = by_gene[gene]
    comment = f"{prev['comment']}; {note}".strip("; ")
    if _clarity(result) >= _clarity(prev["result"]):
        by_gene[gene] = {"gene": gene, "result": result, "comment": comment}
    else:
        by_gene[gene] = {"gene": gene, "result": prev["result"], "comment": comment}
