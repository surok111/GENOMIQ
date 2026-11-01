"""
ClinPGx (бывший PharmGKB) REST API.

Документация: https://api.clinpgx.org/
Лимит: 2 запроса в секунду.
"""

from __future__ import annotations

from ..httputil import HttpError, get_json

CLINPGX_API = "https://api.clinpgx.org/v1/data"
CLINPGX_PAGE = "https://www.clinpgx.org"


def _as_list(payload) -> list:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if data:
            return [data]
        if payload.get("id") or payload.get("accessionId") or payload.get("symbol"):
            return [payload]
    return []


def _join_names(items, key="name") -> str:
    names = []
    for it in items or []:
        if isinstance(it, dict):
            names.append(str(it.get(key) or it.get("symbol") or it.get("term") or ""))
        else:
            names.append(str(it))
    return ", ".join(n for n in names if n)


def fetch_clinpgx(symbol: str) -> dict:
    symbol = symbol.strip().upper()
    gene_id = None
    gene_payload = {}
    try:
        gene_payload_raw = get_json(
            f"{CLINPGX_API}/gene",
            {"symbol": symbol, "view": "base"},
            min_interval=0.55,
        )
        genes = _as_list(gene_payload_raw)
        if genes:
            gene_payload = genes[0]
            gene_id = (
                gene_payload.get("id")
                or gene_payload.get("accessionId")
                or gene_payload.get("objCls")
            )
            if isinstance(gene_id, dict):
                gene_id = gene_id.get("id")
    except HttpError as e:
        if e.status == 404:
            gene_payload = {}
        else:
            raise

    annotations = []
    try:
        ann_raw = get_json(
            f"{CLINPGX_API}/clinicalAnnotation",
            {"location.genes.symbol": symbol, "view": "base"},
            min_interval=0.55,
        )
        for ann in _as_list(ann_raw)[:80]:
            loc = ann.get("location") or {}
            level = ann.get("levelOfEvidence") or {}
            if isinstance(level, dict):
                level_term = level.get("term") or level.get("name") or ""
            else:
                level_term = str(level or "")
            ann_id = ann.get("id") or ann.get("accessionId")
            if not ann_id:
                continue
            annotations.append({
                "annotation_id": str(ann_id),
                "level": level_term,
                "variant": loc.get("name") or loc.get("fingerprint") or "",
                "drugs": _join_names(ann.get("relatedChemicals")),
                "types": ", ".join(str(t) for t in (ann.get("types") or [])),
                "phenotypes": _join_names(ann.get("relatedDiseases")),
                "url": f"{CLINPGX_PAGE}/clinicalAnnotation/{ann_id}",
                "payload": {
                    "level": level_term,
                    "types": ann.get("types"),
                },
            })
    except HttpError as e:
        if e.status != 404:
            raise

    labels = []
    try:
        lab_raw = get_json(
            f"{CLINPGX_API}/label",
            {"source": "fda", "relatedGenes.symbol": symbol, "view": "base"},
            min_interval=0.55,
        )
        for lab in _as_list(lab_raw)[:40]:
            lab_id = lab.get("id") or lab.get("accessionId")
            if not lab_id:
                continue
            labels.append({
                "label_id": str(lab_id),
                "source": lab.get("source") or "FDA",
                "name": lab.get("name") or _join_names(lab.get("relatedChemicals")),
                "url": f"{CLINPGX_PAGE}/label/{lab_id}",
            })
    except HttpError as e:
        if e.status != 404:
            raise

    return {
        "clinpgx_id": str(gene_id) if gene_id else None,
        "name": gene_payload.get("name"),
        "annotations": annotations,
        "labels": labels,
    }
