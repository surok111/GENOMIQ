"""Parse mixed laboratory exports (VCF rows + karyotype + free-text notes).

Returns the same list-of-dicts shape as interpreter.parse_patient_report:
    {"gene": str, "result": str, "comment": str}

Only rsIDs that map to genes in the GenomIQ knowledge base are kept.
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

# CHROM POS ID REF ALT QUAL FILTER INFO FORMAT SAMPLE  (tabs or spaces)
_VCF_ROW = re.compile(
    r"^(?:chr)?\S+\s+\d+\s+(rs\d+)\s+([ACGTN]+)\s+([ACGTN.,]+)\s+\S+\s+\S+\s+\S+\s+(\S+)\s+(\S+)",
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
    """True for .vcf files or mixed lab dumps that embed a VCF header."""
    if path and str(path).lower().endswith(".vcf"):
        return True
    head = text[:8000]
    return (
        "##fileformat=vcf" in head.lower()
        or "[VCF_HEADER]" in head
        or "[KARYOTYPE_REPORT]" in head
    )


def parse_raw_lab_report(text: str) -> list[dict[str, str]]:
    """Extract gene/result pairs from a mixed VCF + karyotype + notes file."""
    by_gene: dict[str, dict[str, str]] = {}
    vcf_hits = _parse_vcf(text)
    _merge_vcf(by_gene, vcf_hits)
    _merge_notes(by_gene, text)
    _merge_karyotype(by_gene, text)
    return list(by_gene.values())


def _parse_vcf(text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _VCF_ROW.match(line)
        if not m:
            continue
        rsid, ref, alt, fmt, sample = m.groups()
        rsid_key = rsid.lower()
        gene = RSID_TO_GENE.get(rsid_key)
        if gene is None:
            continue
        alleles = _alleles_from_gt(ref, alt, fmt, sample)
        if alleles is None:
            continue
        gt_code, pair = alleles
        hits.append(
            {
                "gene": gene,
                "rsid": rsid_key,
                "ref": ref.upper(),
                "alt": alt.split(",")[0].upper(),
                "gt": gt_code,
                "pair": pair,
            }
        )
    return hits


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
    alt_alleles = [a.upper() for a in alt.split(",")]
    letters: list[str] = []
    for tok in tokens[:2]:
        if tok in {".", ""}:
            return None
        try:
            idx = int(tok)
        except ValueError:
            return None
        if idx == 0:
            letters.append(ref.upper())
        elif 1 <= idx <= len(alt_alleles):
            letters.append(alt_alleles[idx - 1])
        else:
            return None
    return gt_raw.replace("|", "/"), f"{letters[0]}/{letters[1]}"


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
            # One clinically relevant SNP per gene in this dump.
            row = rows[0]
            compact = row["pair"].replace("/", "")
            result = compact
            comment = f"{row['rsid']} {row['ref']}>{row['alt']} GT={row['gt']} → {row['pair']}"
        by_gene[gene] = {"gene": gene, "result": result, "comment": comment}


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


def _merge_karyotype(by_gene: dict[str, dict[str, str]], text: str) -> None:
    m = _KARYOTYPE.search(text)
    if not m:
        return
    iscn = m.group(1).rstrip(",")
    by_gene["KARYOTYPE"] = {
        "gene": "KARYOTYPE",
        "result": iscn,
        "comment": "ISCN from KARYOTYPE_REPORT",
    }


def _put(by_gene: dict[str, dict[str, str]], gene: str, result: str, note: str) -> None:
    if gene in by_gene:
        prev = by_gene[gene]
        comment = f"{prev['comment']}; {note}".strip("; ")
        # Notes carry the clinical string the knowledge base tables use (*1/*2, E3/E4, TT).
        by_gene[gene] = {"gene": gene, "result": result, "comment": comment}
    else:
        by_gene[gene] = {"gene": gene, "result": result, "comment": note}
