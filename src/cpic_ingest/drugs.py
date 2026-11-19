"""Drug names taken from the GenomIQ knowledge base. No hardcoded drug list."""

from __future__ import annotations

import json
import re
from typing import Any

from .errors import CpicPersistError

_DRUG_KEYS = {"drug", "drugs", "препарат", "лекарство"}


def _is_drug_key(key: str) -> bool:
    folded = str(key).strip().casefold()
    return folded in _DRUG_KEYS or folded.startswith("drug")


def _split_drug_cell(value: Any) -> list[str]:
    text = str(value or "").replace("*", "").replace("_", "").strip()
    if not text:
        return []
    names = []
    for part in re.split(r"[;|,]", text):
        name = " ".join(part.split()).strip()
        if len(name) >= 2:
            names.append(name)
    return names


def drugs_from_row(row_data: dict) -> list[str]:
    """Drug names from one pharmacogenomics row."""
    names: list[str] = []
    for key, value in row_data.items():
        if _is_drug_key(str(key)):
            names.extend(_split_drug_cell(value))
    return names


def unique_drugs(names: list[str]) -> list[str]:
    """Preserve the first spelling of each drug."""
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(name)
    return unique


def drugs_mentioned(guideline: dict) -> list[str]:
    """Drug names listed on a CPIC guideline payload, when the API sends them."""
    raw = guideline.get("drugs")
    names: list[str] = []
    if isinstance(raw, str):
        names.extend(_split_drug_cell(raw))
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                names.extend(_split_drug_cell(item))
            elif isinstance(item, dict):
                for key in ("drugname", "name", "drug"):
                    if item.get(key):
                        names.extend(_split_drug_cell(item[key]))
                        break
    return unique_drugs(names)


def load_drug_names(conn) -> list[str]:
    """Read distinct drug names from ``kb_pgx`` rows already stored in PostgreSQL."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT row_data FROM kb_pgx")
            fetched = cur.fetchall()
    except Exception as exc:
        raise CpicPersistError("Could not read drug names from kb_pgx") from exc
    names: list[str] = []
    for row in fetched:
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict):
            names.extend(drugs_from_row(payload))
    return unique_drugs(names)
