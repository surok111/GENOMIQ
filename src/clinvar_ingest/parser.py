"""Stream-filter a ClinVar variant_summary table.

``.gz`` files (including ``.tsv.gz`` and ``.txt.gz``) are read with gzip.
Plain ``.tsv`` files are read with no compression. Both use
``pandas.read_csv(..., chunksize=...)`` so the full table is never materialized.
Significance and gene-panel filters run on each chunk before any row becomes
a Python dict.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd

from .errors import ClinVarParseError

PATHOGENIC_SIGNIFICANCE = frozenset({"Pathogenic", "Likely pathogenic"})
_REQUIRED_COLUMNS = ("VariationID", "GeneSymbol", "ClinicalSignificance")
_ASSEMBLY_RANK = {"GRCh38": 0, "GRCh37": 1}


def is_pathogenic(record: dict) -> bool:
    """True only when ClinicalSignificance is exactly Pathogenic or Likely pathogenic."""
    significance = str(record.get("ClinicalSignificance") or "").strip()
    return significance in PATHOGENIC_SIGNIFICANCE


def gene_symbols(value: Any) -> list[str]:
    """Split a ClinVar GeneSymbol cell. Hyphens inside a symbol are kept."""
    text = str(value or "").strip()
    if not text or text == "-":
        return []
    parts: list[str] = []
    for chunk in text.replace("|", ";").replace(",", ";").split(";"):
        symbol = chunk.strip().upper()
        if symbol and symbol != "-":
            parts.append(symbol)
    return parts


def matches_panel(record: dict, panel: set[str]) -> bool:
    """True when any HGNC symbol on the row is in the supplied panel."""
    wanted = {symbol.upper() for symbol in panel}
    return any(symbol in wanted for symbol in gene_symbols(record.get("GeneSymbol")))


def is_retained(record: dict, panel: set[str]) -> bool:
    return is_pathogenic(record) and matches_panel(record, panel)


def assembly_rank(record: dict) -> int:
    """Lower is preferred. GRCh38 wins over GRCh37 for the same VariationID."""
    assembly = str(record.get("Assembly") or "").strip()
    return _ASSEMBLY_RANK.get(assembly, 2)


def _normalize_columns(columns: list[Any]) -> list[str]:
    names: list[str] = []
    for column in columns:
        name = str(column).strip()
        if name.startswith("#") and not name.startswith("RS#"):
            name = name[1:]
        names.append(name)
    return names


def _read_compression(source: str | Path) -> str | None:
    """``gzip`` for a ``.gz`` path, otherwise uncompressed (plain ``.tsv``)."""
    if Path(source).name.lower().endswith(".gz"):
        return "gzip"
    return None


def _iter_frames(source: str | Path, chunksize: int) -> Iterator[pd.DataFrame]:
    if chunksize < 1:
        raise ClinVarParseError("chunksize must be a positive integer")
    try:
        reader = pd.read_csv(
            source,
            sep="\t",
            compression=_read_compression(source),
            chunksize=chunksize,
            dtype=str,
            keep_default_na=False,
            na_values=[],
            low_memory=False,
            encoding="utf-8",
        )
    except Exception as exc:
        raise ClinVarParseError(f"Could not open ClinVar table: {exc.__class__.__name__}") from exc

    try:
        yield from reader
    except ClinVarParseError:
        raise
    except Exception as exc:
        raise ClinVarParseError(f"Could not read ClinVar table: {exc.__class__.__name__}") from exc


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame.columns = _normalize_columns(list(frame.columns))
    missing = [name for name in _REQUIRED_COLUMNS if name not in frame.columns]
    if missing:
        raise ClinVarParseError("ClinVar table is missing columns: " + ", ".join(missing))
    return frame


def _filter_frame(frame: pd.DataFrame, panel: set[str]) -> pd.DataFrame:
    """Rows whose significance and gene tokens pass the same checks as ``is_retained``."""
    significance = frame["ClinicalSignificance"].str.strip()
    pathogenic = frame.loc[significance.isin(PATHOGENIC_SIGNIFICANCE)]
    if pathogenic.empty:
        return pathogenic

    tokens = (
        pathogenic["GeneSymbol"]
        .str.strip()
        .str.upper()
        .str.split(r"[;|,]", regex=True)
        .explode()
        .str.strip()
    )
    matched = tokens.isin(panel)
    if not bool(matched.any()):
        return pathogenic.iloc[0:0]
    keep_labels = pd.unique(tokens.index[matched.to_numpy()])
    return pathogenic.loc[keep_labels]


def _records(frame: pd.DataFrame) -> list[dict]:
    if frame.empty:
        return []
    return frame.to_dict(orient="records")


def iter_variant_chunks(source: str | Path, chunksize: int = 50_000) -> Iterator[list[dict]]:
    """Yield every raw record, one pandas chunk at a time."""
    for frame in _iter_frames(source, chunksize):
        yield _records(_normalize_frame(frame))


def iter_retained_chunks(
    source: str | Path,
    panel: set[str],
    chunksize: int = 50_000,
) -> Iterator[list[dict]]:
    """Yield retained rows per chunk. Rejected rows are never turned into dicts."""
    if not panel:
        raise ClinVarParseError("Gene panel is empty")
    wanted = {symbol.upper() for symbol in panel}
    for frame in _iter_frames(source, chunksize):
        kept = _filter_frame(_normalize_frame(frame), wanted)
        if kept.empty:
            continue
        yield _records(kept)


def iter_retained_records(
    source: str | Path,
    panel: set[str],
    chunksize: int = 50_000,
) -> Iterator[dict]:
    """Yield panel pathogenic/likely-pathogenic rows without holding the file."""
    for rows in iter_retained_chunks(source, panel, chunksize=chunksize):
        yield from rows


def dedupe_variation(records: list[dict], locked_grch38: set[int]) -> list[dict]:
    """One row per VariationID. Keep GRCh38 once it has been seen.

    ``locked_grch38`` is updated with VariationIDs chosen on GRCh38 so a later
    GRCh37 row for the same id is not written over it. The staging primary key
    is VariationID alone, and variant_summary contains one row per assembly.
    """
    chosen: dict[int, dict] = {}
    for record in records:
        raw_id = str(record.get("VariationID") or "").strip()
        if not raw_id.isdigit():
            continue
        variation_id = int(raw_id)
        if variation_id in locked_grch38 and str(record.get("Assembly") or "").strip() != "GRCh38":
            continue
        current = chosen.get(variation_id)
        if current is None or assembly_rank(record) < assembly_rank(current):
            chosen[variation_id] = record
    for variation_id, record in chosen.items():
        if str(record.get("Assembly") or "").strip() == "GRCh38":
            locked_grch38.add(variation_id)
    return list(chosen.values())
