"""HGNC symbols from the local knowledge base. No hardcoded gene list."""

from __future__ import annotations

from pathlib import Path

from genedb.catalog import load_knowledge_genes

from .errors import ClinVarIngestError


def load_hgnc_panel(path: Path | None = None) -> set[str]:
    """Upper-case HGNC symbols (and header aliases) from the knowledge base."""
    genes = load_knowledge_genes(path)
    symbols: set[str] = set()
    for gene in genes:
        primary = str(gene.get("symbol") or "").strip().upper()
        if primary:
            symbols.add(primary)
        for alias in gene.get("aliases") or []:
            token = str(alias).strip().upper()
            if token:
                symbols.add(token)
    if not symbols:
        raise ClinVarIngestError(
            "HGNC gene panel is empty. Build the knowledge base before ClinVar ingest."
        )
    return symbols
