"""Подмешивание живых данных OMIM / ClinVar / ClinPGx в результаты интерпретации."""

from __future__ import annotations

from .store import GeneStore
from .paths import DB_PATH


def attach_live_db(results: list[dict], store: GeneStore | None = None) -> list[dict]:
    if not results:
        return results
    if not DB_PATH.exists() and store is None:
        return results

    own = store is None
    store = store or GeneStore()
    try:
        for item in results:
            snap = store.snapshot_for_gene(item.get("gene", ""))
            if snap:
                item["live_db"] = snap
    finally:
        if own:
            store.close()
    return results
