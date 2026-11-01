"""
ClinVar через NCBI E-utilities (публичный API).

Документация: https://www.ncbi.nlm.nih.gov/clinvar/docs/programmatic_access/
"""

from __future__ import annotations

import os
import re

from ..httputil import get_json

NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CLINVAR_URL = "https://www.ncbi.nlm.nih.gov/clinvar/variation/{id}/"


def _ncbi_params() -> dict:
    params = {"retmode": "json", "tool": "genomiq"}
    email = os.environ.get("NCBI_EMAIL")
    api_key = os.environ.get("NCBI_API_KEY")
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def _search_ids(symbol: str, extra_term: str, retmax: int) -> list[str]:
    params = _ncbi_params()
    term = f"{symbol}[gene]"
    if extra_term:
        term = f"{term} AND {extra_term}"
    data = get_json(
        f"{NCBI_EUTILS}/esearch.fcgi",
        {**params, "db": "clinvar", "term": term, "retmax": retmax, "sort": "relevance"},
        min_interval=0.4,
    )
    return (data.get("esearchresult") or {}).get("idlist") or []


def _count_term(term: str) -> int:
    data = get_json(
        f"{NCBI_EUTILS}/esearch.fcgi",
        {**_ncbi_params(), "db": "clinvar", "term": term, "retmax": 0},
        min_interval=0.4,
    )
    return int((data.get("esearchresult") or {}).get("count") or 0)


def _classification_stats(symbol: str) -> dict:
    """Полные счётчики ClinVar. Фильтры clinsig_*[prop] проверены через esearch."""
    stats = {
        "total": _count_term(f"{symbol}[gene]"),
        "pathogenic": _count_term(f"{symbol}[gene] AND clinsig_pathogenic[prop]"),
        "likely_pathogenic": _count_term(f"{symbol}[gene] AND clinsig_likely_pathogenic[prop]"),
        "vus": _count_term(f"{symbol}[gene] AND clinsig_vus[prop]"),
        "likely_benign": _count_term(f"{symbol}[gene] AND clinsig_likely_benign[prop]"),
        "benign": _count_term(f"{symbol}[gene] AND clinsig_benign[prop]"),
        "conflicting": 0,
        "other": 0,
    }
    known = (
        stats["pathogenic"] + stats["likely_pathogenic"] + stats["vus"]
        + stats["likely_benign"] + stats["benign"]
    )
    stats["other"] = max(0, stats["total"] - known)
    return stats


def fetch_clinvar(symbol: str, max_variants: int = 120) -> tuple[list[dict], dict]:
    symbol = symbol.strip().upper()
    pathogenic_term = "(clinsig_pathogenic[prop] OR clinsig_likely_pathogenic[prop])"
    ids = _search_ids(symbol, pathogenic_term, min(80, max_variants))
    extra = _search_ids(symbol, "single_gene[prop]", max_variants)
    merged = []
    seen = set()
    for vid in ids + extra:
        if vid not in seen:
            seen.add(vid)
            merged.append(vid)
        if len(merged) >= max_variants:
            break

    stats = _classification_stats(symbol)
    if not merged:
        return [], stats

    variants = []
    for i in range(0, len(merged), 40):
        chunk = merged[i:i + 40]
        summary = get_json(
            f"{NCBI_EUTILS}/esummary.fcgi",
            {**_ncbi_params(), "db": "clinvar", "id": ",".join(chunk)},
            min_interval=0.4,
        )
        result = summary.get("result") or {}
        for uid in chunk:
            rec = result.get(str(uid)) or {}
            germ = rec.get("germline_classification") or {}
            if isinstance(germ, dict):
                classification = germ.get("description") or ""
                review_status = germ.get("review_status") or ""
            else:
                classification = str(germ or "")
                review_status = ""
            traits = []
            if isinstance(germ, dict):
                traits.extend(germ.get("trait_set") or [])
            traits.extend(rec.get("trait_set") or [])
            seen_traits = []
            for t in traits:
                name = t.get("trait_name") if isinstance(t, dict) else ""
                if name and name not in seen_traits:
                    seen_traits.append(name)
            conditions = "; ".join(seen_traits)
            rsid = ""
            for vs in rec.get("variation_set") or []:
                for ident in vs.get("variation_xrefs") or vs.get("other_identifiers") or []:
                    db = (ident.get("db_source") or ident.get("db") or "").lower()
                    if db in ("dbsnp", "dbSNP"):
                        rsid = ident.get("id") or ident.get("db_id") or ""
                        break
                if not rsid:
                    canonical = vs.get("canonical_spdi") or vs.get("variation_name") or ""
                    m = re.search(r"rs\d+", str(canonical), re.I)
                    if m:
                        rsid = m.group(0)
            variants.append({
                "variation_id": str(uid),
                "title": rec.get("title"),
                "classification": classification,
                "review_status": review_status,
                "variation_type": rec.get("variation_type") or rec.get("obj_type"),
                "rsid": rsid,
                "conditions": conditions[:500],
                "url": CLINVAR_URL.format(id=uid),
            })

    return variants, stats
