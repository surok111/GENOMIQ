"""
OMIM: официальный REST (при наличии OMIM_API_KEY) и fallback через NCBI E-utilities.

Документация: https://omim.org/help/api
Запрос ключа: https://omim.org/api
Пример записи: https://omim.org/entry/601769
"""

from __future__ import annotations

import os

from ..httputil import HttpError, get_json

OMIM_API = "https://api.omim.org/api"
NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _ncbi_params() -> dict:
    params = {"retmode": "json", "tool": "genomiq"}
    email = os.environ.get("NCBI_EMAIL")
    api_key = os.environ.get("NCBI_API_KEY")
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def fetch_omim(symbol: str) -> list[dict]:
    symbol = symbol.strip().upper()
    key = os.environ.get("OMIM_API_KEY", "").strip()
    if key:
        try:
            entries = _fetch_official(symbol, key)
            if entries:
                return entries
        except HttpError as e:
            if e.status not in (401, 403, 429):
                raise
        return _fetch_ncbi(symbol)
    return _fetch_ncbi(symbol)


def _fetch_official(symbol: str, api_key: str) -> list[dict]:
    search = get_json(
        f"{OMIM_API}/entry/search",
        {
            "search": f"approved_gene_symbol:{symbol}",
            "start": 0,
            "limit": 8,
            "format": "json",
            "apiKey": api_key,
        },
        min_interval=0.5,
    )
    search_response = (
        search.get("omim", {}).get("searchResponse", {})
        or search.get("searchResponse", {})
    )
    entries = search_response.get("entryList") or []
    mim_numbers = []
    for item in entries:
        entry = item.get("entry") or item
        mim = entry.get("mimNumber")
        if mim:
            mim_numbers.append(str(mim))
    if not mim_numbers:
        return _fetch_ncbi(symbol)

    result = get_json(
        f"{OMIM_API}/entry",
        {
            "mimNumber": ",".join(mim_numbers[:6]),
            "include": "geneMap,allelicVariantList,existFlags",
            "format": "json",
            "apiKey": api_key,
        },
        min_interval=0.5,
    )
    payload = result.get("omim", {}).get("entryList") or result.get("entryList") or []
    out = []
    for item in payload:
        entry = item.get("entry") or item
        mim = str(entry.get("mimNumber", ""))
        titles = entry.get("titles") or {}
        gene_map = (entry.get("geneMap") or {})
        phenotypes = []
        for ph in gene_map.get("phenotypeMapList") or []:
            pm = ph.get("phenotypeMap") or ph
            phenotypes.append({
                "phenotype": pm.get("phenotype"),
                "mim_number": pm.get("phenotypeMimNumber"),
                "mapping_key": pm.get("phenotypeMappingKey"),
                "inheritance": pm.get("phenotypeInheritance"),
            })
        allelic = []
        for av in entry.get("allelicVariantList") or []:
            rec = av.get("allelicVariant") or av
            allelic.append({
                "number": rec.get("number"),
                "name": rec.get("name"),
                "mutations": rec.get("mutations"),
                "dbSnps": rec.get("dbSnps"),
                "clinvarAccessions": rec.get("clinvarAccessions"),
            })
        out.append({
            "mim_number": mim,
            "title": titles.get("preferredTitle") or titles.get("title"),
            "prefix": entry.get("prefix"),
            "phenotypes": phenotypes,
            "allelic_variants": allelic[:40],
            "source": "omim_api",
            "url": f"https://omim.org/entry/{mim}",
        })
    return out


def _fetch_ncbi(symbol: str) -> list[dict]:
    """Публичный доступ к OMIM через NCBI Entrez (без ключа OMIM)."""
    params = _ncbi_params()
    search = get_json(
        f"{NCBI_EUTILS}/esearch.fcgi",
        {
            **params,
            "db": "omim",
            "term": f"{symbol}[gene] AND human[organism]",
            "retmax": 8,
        },
        min_interval=0.4,
    )
    ids = (search.get("esearchresult") or {}).get("idlist") or []
    if not ids:
        gene_search = get_json(
            f"{NCBI_EUTILS}/esearch.fcgi",
            {
                **params,
                "db": "gene",
                "term": f"{symbol}[sym] AND Homo sapiens[organism]",
                "retmax": 1,
            },
            min_interval=0.4,
        )
        gene_ids = (gene_search.get("esearchresult") or {}).get("idlist") or []
        if gene_ids:
            summary = get_json(
                f"{NCBI_EUTILS}/esummary.fcgi",
                {**params, "db": "gene", "id": gene_ids[0]},
                min_interval=0.4,
            )
            rec = (summary.get("result") or {}).get(str(gene_ids[0])) or {}
            mim = rec.get("MIM") or rec.get("mim")
            extras = rec.get("otheraliases") or ""
            if mim:
                ids = [str(mim)]
            gene_meta = {
                "chromosome": rec.get("chromosome"),
                "summary": rec.get("summary"),
                "name": rec.get("description") or rec.get("nomenclaturename"),
                "aliases": [a.strip() for a in extras.split(",") if a.strip()],
            }
        else:
            gene_meta = {}
    else:
        gene_meta = {}

    if not ids:
        return []

    summary = get_json(
        f"{NCBI_EUTILS}/esummary.fcgi",
        {**params, "db": "omim", "id": ",".join(ids)},
        min_interval=0.4,
    )
    result = summary.get("result") or {}
    out = []
    for uid in result.get("uids") or ids:
        rec = result.get(str(uid)) or {}
        mim = str(rec.get("uid") or uid)
        out.append({
            "mim_number": mim,
            "title": rec.get("title"),
            "prefix": None,
            "phenotypes": [],
            "allelic_variants": [],
            "source": "ncbi_omim",
            "url": f"https://omim.org/entry/{mim}",
            "gene_meta": gene_meta,
        })
    if out and gene_meta:
        out[0]["gene_meta"] = gene_meta
    return out
