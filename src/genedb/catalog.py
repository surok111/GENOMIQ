"""Список генов из локальной базы знаний (parsed_knowledge_base_clean.json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .paths import KB_CLEAN

# Разделитель — типографское тире (— / –), не дефис внутри символа гена (HLA-DRB1)
RE_HEADER = re.compile(r"^([A-Z0-9/* \-]+)\s+[—–]")


def extract_gene_symbols(header: str) -> list[str]:
    m = RE_HEADER.match(header.strip())
    raw = m.group(1).strip() if m else (header.split()[0] if header.split() else header)
    parts = re.split(r"\s*/\s*", raw)
    symbols = []
    for part in parts:
        token = part.strip().upper()
        token = re.sub(r"\s+", "-", token) if "HLA" in token else token.replace(" ", "")
        if token:
            symbols.append(token)
    return symbols or [raw.strip().upper()]


def load_knowledge_genes(path: Path | None = None) -> list[dict]:
    kb_path = path or KB_CLEAN
    if not kb_path.exists():
        return []
    with open(kb_path, encoding="utf-8") as f:
        base = json.load(f)
    genes = []
    seen = set()
    for group in base:
        group_name = group.get("group", "")
        for gene in group.get("genes", []):
            header = gene.get("header", "")
            symbols = extract_gene_symbols(header)
            primary = symbols[0]
            if primary in seen:
                continue
            seen.add(primary)
            genes.append({
                "symbol": primary,
                "aliases": symbols[1:],
                "name": header,
                "kb_group": group_name,
            })
    return genes
