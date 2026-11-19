"""Normalize CPIC JSON into staging rows.

A guideline change is a new id or a higher version. Publication year is stored
and is never used to decide whether the record changed.
"""

from __future__ import annotations

from typing import Any


def guideline_action(stored_version: int | None, new_version: int) -> str:
    """``insert``, ``update``, or ``unchanged``."""
    if stored_version is None:
        return "insert"
    if new_version > stored_version:
        return "update"
    return "unchanged"


def _as_int(value: Any) -> int | None:
    if value is None or value is False:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    return int(text)


def _publication(row: dict) -> dict:
    publication = row.get("publication")
    if isinstance(publication, list):
        publication = publication[0] if publication else None
    return publication if isinstance(publication, dict) else {}


def normalize_guideline(row: dict) -> dict | None:
    """Return the persisted guideline fields, or None when id or version is missing."""
    guideline_id = _as_int(row.get("id"))
    version = _as_int(row.get("version"))
    if guideline_id is None or version is None:
        return None
    publication = _publication(row)
    pmid = publication.get("pmid")
    year = _as_int(publication.get("year"))
    clinpgxid = row.get("clinpgxid")
    return {
        "id": guideline_id,
        "version": version,
        "clinpgxid": None if clinpgxid in (None, "") else str(clinpgxid),
        "name": _text(row.get("name")),
        "url": _text(row.get("url")),
        "publication_pmid": None if pmid in (None, "") else str(pmid),
        "publication_year": year,
        "raw_payload": row,
    }


def normalize_recommendation(row: dict, fallback_drug: str | None = None) -> dict | None:
    """Return the persisted recommendation fields, or None when the id is missing."""
    recommendation_id = _as_int(row.get("recommendationid"))
    if recommendation_id is None:
        return None
    drugname = _text(row.get("drugname")) or _text(fallback_drug)
    return {
        "recommendationid": recommendation_id,
        "lookupkey": row.get("lookupkey"),
        "drugname": drugname,
        "guidelinename": _text(row.get("guidelinename")),
        "guidelineurl": _text(row.get("guidelineurl")),
        "raw_payload": row,
    }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None
