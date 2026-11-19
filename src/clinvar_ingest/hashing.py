"""Deterministic content hash for a ClinVar variant_summary row."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

# Only these source fields participate in the hash. Order here is documentation;
# serialization sorts keys.
HASH_FIELDS: tuple[str, ...] = (
    "VariationID",
    "RS#",
    "GeneSymbol",
    "GeneID",
    "ClinicalSignificance",
    "ReviewStatus",
    "LastEvaluated",
    "Origin",
    "Name",
    "Type",
    "Assembly",
    "Start",
    "Stop",
    "ReferenceAllele",
    "AlternateAllele",
)

# variant_summary.txt.gz annotates a few headers. The hash key stays the
# canonical name from the ingestion spec.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "RS#": ("RS#", "RS# (dbSNP)"),
}


def _json_value(value: Any) -> Any:
    """Value safe for json.dumps. Missing and NaN become JSON null."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    item = getattr(value, "item", None)
    if callable(item) and not isinstance(value, (str, bytes, dict, list)):
        try:
            return _json_value(item())
        except (ValueError, TypeError):
            return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    return str(value)


def _field_value(record: dict, field: str) -> Any:
    keys = _FIELD_ALIASES.get(field, (field,))
    for key in keys:
        if key in record and record[key] is not None:
            return _json_value(record[key])
    return None


def hash_document(record: dict) -> dict[str, Any]:
    """The exact object that is hashed. Unlisted keys are omitted."""
    return {field: _field_value(record, field) for field in HASH_FIELDS}


def canonical_hash(record: dict) -> str:
    """SHA-256 hex digest of the canonical ClinVar fields.

    ``json.dumps(..., sort_keys=True, separators=(",", ":"))`` makes the
    digest independent of dict order and of any field that is not in
    ``HASH_FIELDS``.
    """
    encoded = json.dumps(
        hash_document(record),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
