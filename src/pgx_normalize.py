"""Additive pharmacogenomics normalization (schema 1).

The source tables stay in ``sections[].tables`` and ``sections[].other_tables``.
This module adds ``gene["normalization"]`` without rewriting clinical text.

Compatibility:
- Existing readers that walk ``tables``, ``bullets``, and ``pharmacogenomics``
  keep working.
- ``use_exact_matcher`` is true only when a gene has drug-recommendation rows
  and every genotype reference cell parsed. Other genes stay on the legacy
  matcher.
- Schema 1 is rebuilt in place. A newer version replaces the object; raw
  table cells are never migrated by editing them.

Equivalences recorded here are only those written in the source cell:
parenthetical ``521 CC`` aliases, and star-diplotype allele order
(``*1/*2`` and ``*2/*1``). Copy-number suffixes such as ``xN`` are part of
the allele and are never dropped.
"""

from __future__ import annotations

import re
from typing import Any, Optional

SCHEMA_VERSION = 1

PHENOTYPE_CODE = r"IM|PM|UM|NM|RM"
PHENOTYPE_CELL = re.compile(
    rf"^(?:{PHENOTYPE_CODE})(?:\s*/\s*(?:{PHENOTYPE_CODE}))*(?:\s*\([^)]*\))?$",
    re.IGNORECASE,
)
PAREN_CODES = re.compile(rf"^({PHENOTYPE_CODE})(?:/({PHENOTYPE_CODE}))*$", re.IGNORECASE)
STAR_ALLELE = re.compile(r"^\*(\d+)([A-Za-z]*?)(xN|x\d+)?$", re.IGNORECASE)
NUCLEOTIDE = re.compile(r"^[ACGT]{2}$", re.IGNORECASE)
ALIAS_521 = re.compile(r"^521\s*([ACGT]{2})$", re.IGNORECASE)
RSID = re.compile(r"rs\d+", re.IGNORECASE)
RSID_NOTE = re.compile(r"(rs\d+)\s*(?:\(([^)]*)\))?", re.IGNORECASE)
TRAILING_PAREN = re.compile(r"^(.*)\(([^)]*)\)\s*$")
BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
STAR_IN_TEXT = re.compile(
    r"\*(\d+)([A-Za-z]*?)(xN|x\d+)?/\*(\d+)([A-Za-z]*?)(xN|x\d+)?",
    re.IGNORECASE,
)


def strip_md(value: str) -> str:
    if not value:
        return ""
    return BOLD.sub(r"\1", str(value)).strip()


def _provenance(source_file: str, gene: str, section: dict, table_index: int, row_index: Optional[int], column: str = "") -> dict:
    return {
        "file": source_file,
        "gene": gene,
        "section_code": section.get("code", ""),
        "section_title": section.get("title", ""),
        "table_index": table_index,
        "row_index": row_index,
        "column": column,
    }


def _warn(warnings: list, code: str, message: str, provenance: dict) -> None:
    warnings.append({"code": code, "message": message, "provenance": provenance})


def _allele_from_match(number: str, suffix: str, copy: str) -> dict:
    suf = suffix or ""
    return {
        "id": f"*{number}{suf}",
        "copy": copy or "",
    }


def parse_star_allele(part: str) -> Optional[dict]:
    match = STAR_ALLELE.fullmatch(part.strip())
    if not match:
        return None
    return _allele_from_match(match.group(1), match.group(2) or "", match.group(3) or "")


def parse_star_diplotype(token: str) -> Optional[dict]:
    parts = [p.strip() for p in token.strip().split("/")]
    if len(parts) != 2:
        return None
    alleles = [parse_star_allele(p) for p in parts]
    if any(a is None for a in alleles):
        return None
    return {
        "raw": token.strip(),
        "normalized": re.sub(r"\s+", "", token).lower(),
        "kind": "star_diplotype",
        "alleles": alleles,
        "key": _star_key(alleles),
    }


def _star_key(alleles: list[dict]) -> list[str]:
    parts = [f"{a['id'].upper()}|{a['copy'].upper()}" for a in alleles]
    return sorted(parts)


def parse_nucleotide_token(token: str) -> Optional[dict]:
    match = NUCLEOTIDE.fullmatch(token.strip())
    if not match:
        return None
    letters = token.strip().upper()
    return {
        "raw": token.strip(),
        "normalized": "".join(sorted(letters)),
        "kind": "nucleotide",
        "alleles": [{"id": letters[0], "copy": ""}, {"id": letters[1], "copy": ""}],
        "key": ["NT:" + "".join(sorted(letters))],
    }


def parse_521_alias(token: str) -> Optional[dict]:
    match = ALIAS_521.fullmatch(token.strip())
    if not match:
        return None
    nuc = parse_nucleotide_token(match.group(1))
    if nuc is None:
        return None
    nuc = dict(nuc)
    nuc["raw"] = token.strip()
    nuc["alias_of"] = nuc["normalized"]
    return nuc


def _split_genotype_body(body: str) -> list[str]:
    text = body.strip()
    if re.fullmatch(r"[ACGT]{2}(?:\s*\+\s*[ACGT]{2})+", text, re.IGNORECASE):
        return [p.strip() for p in re.split(r"\s*\+\s*", text)]
    if re.fullmatch(r"[ACGT]{2}(?:\s*/\s*[ACGT]{2})+", text, re.IGNORECASE):
        return [p.strip() for p in re.split(r"\s*/\s*", text)]
    if "," in text:
        return [p.strip() for p in text.split(",") if p.strip()]
    return [text] if text else []


def parse_star_allele_token(token: str) -> Optional[dict]:
    allele = parse_star_allele(token.strip())
    if allele is None:
        return None
    return {
        "raw": token.strip(),
        "normalized": token.strip().lower(),
        "kind": "star_allele",
        "alleles": [allele],
        "key": [f"{allele['id'].upper()}|{allele['copy'].upper()}"],
    }


def _parse_token(token: str) -> Optional[dict]:
    return parse_star_diplotype(token) or parse_nucleotide_token(token) or parse_star_allele_token(token)


def _phenotype_codes_in(text: str) -> list[str]:
    return [m.group(0).upper() for m in re.finditer(PHENOTYPE_CODE, text, re.IGNORECASE)]


def parse_genotype_cell(raw: str) -> dict:
    """Parse one genotype cell. ``raw`` is preserved on the result."""
    original = raw if raw is not None else ""
    text = strip_md(original).strip()
    base = {
        "raw": original,
        "text": text,
        "kind": "unparsed",
        "scope": "unparsed",
        "tokens": [],
        "aliases": [],
        "phenotype_codes": [],
        "condition": "",
        "label": "",
    }
    if text in ("", "—", "-", "–"):
        base["kind"] = "none"
        base["scope"] = "none"
        return base
    if text.lower() in ("все", "all"):
        base["kind"] = "all"
        base["scope"] = "all"
        return base

    if PHENOTYPE_CELL.fullmatch(text):
        codes = _phenotype_codes_in(text.split("(")[0])
        base["phenotype_codes"] = codes
        paren = TRAILING_PAREN.fullmatch(text)
        inside = paren.group(2).strip() if paren else ""
        if inside:
            qualifier = _parse_token(inside)
            if qualifier is not None:
                base["tokens"] = [qualifier]
                base["kind"] = "genotypes"
                base["scope"] = "genotype"
                return base
            base["condition"] = inside
            base["kind"] = "conditional"
            base["scope"] = "conditional"
            return base
        base["kind"] = "phenotype"
        base["scope"] = "phenotype"
        return base

    rsid_parts = [p.strip() for p in text.split(",") if p.strip()]
    if rsid_parts and all(RSID.fullmatch(p) for p in rsid_parts):
        base["kind"] = "variant_ids"
        base["scope"] = "variant"
        base["tokens"] = [
            {"raw": p, "normalized": p.lower(), "kind": "rsid", "alleles": [], "key": [f"RS:{p.lower()}"]}
            for p in rsid_parts
        ]
        return base

    aliases: list[dict] = []
    body = text
    label = ""
    paren = TRAILING_PAREN.fullmatch(text)
    if paren:
        inside = paren.group(2).strip()
        alias = parse_521_alias(inside)
        if alias is not None:
            aliases.append(alias)
            body = paren.group(1).strip().rstrip(",").strip()
        else:
            maybe = _parse_token(inside)
            if maybe is None and not PHENOTYPE_CELL.fullmatch(inside):
                # Amino-acid or prose label, not a second genotype.
                label = inside
                body = paren.group(1).strip()

    solo_alias = parse_521_alias(body)
    if solo_alias is not None:
        base["tokens"] = []
        base["aliases"] = aliases + [solo_alias]
        base["label"] = label
        base["kind"] = "genotypes"
        base["scope"] = "genotype"
        return base

    parts = _split_genotype_body(body)
    tokens = [_parse_token(p) for p in parts]
    if parts and all(tok is not None for tok in tokens):
        base["tokens"] = tokens
        base["aliases"] = aliases
        base["label"] = label
        base["kind"] = "genotypes"
        base["scope"] = "genotype"
        return base

    base["label"] = label
    base["aliases"] = aliases
    return base


def _column(row: dict, *needles: str) -> tuple[str, str]:
    for key, value in row.items():
        low = key.strip().lower()
        if any(n in low for n in needles):
            return key, value if value is not None else ""
    return "", ""


def _drug_names(raw: str) -> list[str]:
    text = strip_md(raw)
    if not text or text in ("—", "-", "–"):
        return []
    return [p.strip() for p in text.split(",") if p.strip()]


def classify_table(headers: list[str]) -> str:
    """Return drug_recommendation, genotype_reference, identity_reference, substrate_reference, pharmacogenomics, or review."""
    low = [h.strip().lower() for h in headers]
    has_drug_col = any(h in ("препарат", "лекарство", "drug", "drugs") or h.startswith("препарат") for h in low)
    has_gt = any(h.startswith("генотип") or h in ("genotype", "аллели", "alleles") for h in low)
    has_pheno = any("фенотип" in h or h == "phenotype" for h in low)
    has_risk = any("риск" in h or h == "acmg" or "функц" in h for h in low)
    has_param = any(h == "параметр" for h in low)
    has_substrate = any("субстрат" in h for h in low)
    has_pgx = any(h in ("drug", "drugs", "association") for h in low) and any(
        "p-value" in h or h == "sig" or "phenotype" in h for h in low
    )
    if has_pgx and not has_drug_col:
        return "pharmacogenomics"
    if has_drug_col and has_gt:
        return "drug_recommendation"
    if has_drug_col:
        return "review"
    if has_gt and (has_pheno or has_risk):
        return "genotype_reference"
    if has_gt:
        return "genotype_reference"
    if has_param:
        return "identity_reference"
    if has_substrate:
        return "substrate_reference"
    return "review"


def _label_codes(label: str) -> tuple[list[str], bool]:
    text = strip_md(label)
    match = re.search(r"\(([^)]*)\)\s*$", text)
    if not match or not PAREN_CODES.fullmatch(match.group(1).strip()):
        return [], False
    codes = _phenotype_codes_in(match.group(1))
    return codes, len(codes) > 1


def _extract_variants(row: dict, provenance: dict) -> list[dict]:
    found = []
    for key, value in row.items():
        for match in RSID_NOTE.finditer(str(value)):
            note = (match.group(2) or "").strip()
            star = ""
            if note.startswith("*"):
                star = note.split()[0]
            found.append({
                "rsid": match.group(1),
                "note": note,
                "star": star,
                "source_column": key,
                "source_cell": value,
                "provenance": provenance,
            })
    return found


def classify_bullet(raw: str) -> dict:
    text = strip_md(raw)
    parsed = {
        "raw": raw,
        "text": text,
        "scope": "gene",
        "genotype": None,
        "reason": "no explicit genotype; kept as gene-level information",
    }
    orphan = re.match(r"^(Риск|Рекомендация)\s*:", text, re.IGNORECASE)
    if orphan:
        parsed["scope"] = "unresolved"
        parsed["reason"] = "bullet has no genotype anchor; parent list context was not preserved by the parser"
        return parsed

    headed = re.match(r"^(.+?)\s*(?:\(([^)]*)\))?\s*:\s+\S", text)
    if headed:
        body = headed.group(1).strip()
        cell = parse_genotype_cell(body)
        if cell["kind"] == "genotypes" and cell["tokens"]:
            parsed["scope"] = "genotype"
            parsed["genotype"] = cell
            parsed["reason"] = "explicit genotype list in the bullet"
            return parsed

    if re.search(r"метаболист|metabolizer", text, re.IGNORECASE) or re.search(r"\*\d+", text):
        parsed["scope"] = "unresolved"
        parsed["reason"] = "phenotype wording or allele mention without an explicit diplotype or nucleotide list"
        return parsed
    return parsed


def _narrow_genotype_warning(cell: dict, risk_text: str, provenance: dict, warnings: list) -> None:
    if cell["kind"] != "genotypes" or len(cell["tokens"]) < 2:
        return
    named = [m.group(0) for m in STAR_IN_TEXT.finditer(strip_md(risk_text))]
    token_norms = {t["normalized"] for t in cell["tokens"] if t["kind"] == "star_diplotype"}
    for name in named:
        norm = re.sub(r"\s+", "", name).lower()
        if norm in token_norms and len(token_norms) > 1:
            _warn(
                warnings,
                "risk_names_narrower_genotype",
                f"Shared risk text names {name}, which is only one of {', '.join(t['raw'] for t in cell['tokens'])}.",
                provenance,
            )


def _iter_source_tables(gene: dict):
    for section in gene.get("sections") or []:
        for key in ("tables", "other_tables", "pharmacogenomics"):
            for index, table in enumerate(section.get(key) or []):
                yield section, key, index, table


def build_normalization(gene: dict, source_file: str = "", group_name: str = "") -> dict:
    symbol = ""
    try:
        from genedb.catalog import extract_gene_symbols
        symbols = extract_gene_symbols(gene.get("header", ""))
        symbol = symbols[0] if symbols else ""
    except Exception:
        symbol = ""
    if not symbol:
        header = gene.get("header", "")
        symbol = header.split("—")[0].split("–")[0].strip().split()[0] if header else ""

    warnings: list[dict] = []
    errors: list[dict] = []
    reference: list[dict] = []
    drugs: list[dict] = []
    review: list[dict] = []
    bullets: list[dict] = []
    variants: list[dict] = []
    accounted = 0
    expected = 0
    preserved_pgx = 0

    if not symbol:
        errors.append({
            "code": "missing_gene_symbol",
            "message": "Gene header did not yield a symbol.",
            "provenance": {"file": source_file, "gene": gene.get("header", ""), "section_code": "", "section_title": "", "table_index": None, "row_index": None, "column": ""},
        })

    for section, bucket, index, table in _iter_source_tables(gene):
        expected += 1
        headers = list(table.get("headers") or [])
        kind = "pharmacogenomics" if bucket == "pharmacogenomics" else classify_table(headers)
        if bucket == "pharmacogenomics":
            kind = "pharmacogenomics"
        rows = table.get("rows") or []
        table_prov = _provenance(source_file, symbol, section, index, None)
        if kind == "pharmacogenomics":
            preserved_pgx += 1
            accounted += 1
            continue
        if kind == "review":
            review.append({
                "classification": "review",
                "headers": headers,
                "rows": rows,
                "provenance": table_prov,
            })
            _warn(warnings, "ambiguous_table_classification", f"Headers {headers} were not classified as reference or drug recommendations.", table_prov)
            accounted += 1
            continue

        if not rows:
            target = drugs if kind == "drug_recommendation" else reference
            target.append({
                "role": kind,
                "headers": headers,
                "row": None,
                "empty": True,
                "provenance": table_prov,
            })
            accounted += 1
            continue

        for row_index, row in enumerate(rows):
            prov = _provenance(source_file, symbol, section, index, row_index)
            if kind == "drug_recommendation":
                drug_key, drug_raw = _column(row, "препарат", "лекарство", "drug")
                gt_key, gt_raw = _column(row, "генотип", "genotype")
                rec_key, rec_raw = _column(row, "рекомендац", "эффект", "effect")
                src_key, src_raw = _column(row, "источник", "source")
                parsed = parse_genotype_cell(gt_raw)
                names = _drug_names(drug_raw)
                record = {
                    "role": "drug_recommendation",
                    "headers": headers,
                    "row": row,
                    "drug_column": drug_key,
                    "drug_raw": drug_raw,
                    "drugs": names,
                    "genotype_column": gt_key,
                    "genotype_raw": gt_raw,
                    "genotype": parsed,
                    "recommendation_column": rec_key,
                    "recommendation_raw": rec_raw,
                    "source_column": src_key,
                    "source_raw": src_raw,
                    "scope": parsed["scope"],
                    "provenance": {**prov, "column": gt_key},
                }
                drugs.append(record)
                if not names:
                    _warn(warnings, "drug_recommendation_missing_drug", "Drug recommendation row has no drug name.", record["provenance"])
                if parsed["kind"] == "unparsed":
                    _warn(warnings, "row_not_normalized", f"Genotype cell could not be normalized: {gt_raw}", record["provenance"])
                if parsed["scope"] == "conditional":
                    _warn(
                        warnings,
                        "conditional_recommendation_not_evaluated",
                        f"Row requires an additional condition ({parsed['condition']}) that this gene section does not define.",
                        record["provenance"],
                    )
            elif kind == "genotype_reference":
                gt_key, gt_raw = _column(row, "генотип", "genotype", "аллел")
                ph_key, ph_raw = _column(row, "фенотип", "phenotype")
                fn_key, fn_raw = _column(row, "функц")
                risk_key, risk_raw = _column(row, "риск")
                acmg_key, acmg_raw = _column(row, "acmg")
                parsed = parse_genotype_cell(gt_raw)
                codes, ambiguous = _label_codes(ph_raw)
                record = {
                    "role": "genotype_phenotype",
                    "headers": headers,
                    "row": row,
                    "genotype_column": gt_key,
                    "genotype_raw": gt_raw,
                    "genotype": parsed,
                    "phenotype_column": ph_key,
                    "phenotype_raw": ph_raw,
                    "phenotype_codes": codes,
                    "phenotype_codes_ambiguous": ambiguous,
                    "function_raw": fn_raw,
                    "risk_raw": risk_raw,
                    "acmg_raw": acmg_raw,
                    "provenance": {**prov, "column": gt_key},
                }
                reference.append(record)
                if parsed["kind"] == "unparsed":
                    _warn(warnings, "row_not_normalized", f"Genotype cell could not be normalized: {gt_raw}", record["provenance"])
                elif parsed["kind"] == "genotypes":
                    _narrow_genotype_warning(parsed, risk_raw, record["provenance"], warnings)
                if ambiguous:
                    _warn(
                        warnings,
                        "combined_phenotype_label",
                        f"Phenotype label names more than one code and does not assign them to individual genotypes: {ph_raw}",
                        record["provenance"],
                    )
            else:
                role = "identity" if kind == "identity_reference" else "substrate" if kind == "substrate_reference" else "other_reference"
                record = {
                    "role": role,
                    "headers": headers,
                    "row": row,
                    "provenance": prov,
                }
                reference.append(record)
                if role == "identity":
                    variants.extend(_extract_variants(row, prov))
        accounted += 1

    if accounted != expected:
        errors.append({
            "code": "table_coverage",
            "message": f"Accounted for {accounted} of {expected} source tables.",
            "provenance": {"file": source_file, "gene": symbol, "section_code": "", "section_title": "", "table_index": None, "row_index": None, "column": ""},
        })

    for section in gene.get("sections") or []:
        for bullet_index, bullet in enumerate(section.get("bullets") or []):
            item = classify_bullet(bullet)
            item["provenance"] = {
                "file": source_file,
                "gene": symbol,
                "section_code": section.get("code", ""),
                "section_title": section.get("title", ""),
                "table_index": None,
                "row_index": bullet_index,
                "column": "bullet",
            }
            bullets.append(item)
            if item["scope"] == "unresolved":
                _warn(warnings, "bullet_without_genotype_association", item["reason"] + f": {item['text'][:160]}", item["provenance"])

    _warn_conflicts(reference, warnings)
    _warn_drug_reference_gaps(reference, drugs, bullets, warnings)

    genotype_rows = [r for r in reference if r.get("role") == "genotype_phenotype"]
    unparsed_rows = [r for r in genotype_rows if (r.get("genotype") or {}).get("kind") == "unparsed"]
    use_exact = bool(drugs) and bool(genotype_rows) and not unparsed_rows
    if drugs and unparsed_rows:
        _warn(
            warnings,
            "exact_matcher_disabled",
            "Drug recommendations exist, but a genotype reference cell did not normalize. Legacy matching remains in use for this gene.",
            unparsed_rows[0]["provenance"],
        )

    # Structural warnings for genes that do not use the exact matcher would
    # flag ordinary non-PGx notations (Val/Val, amino-acid labels). Those rows
    # stay in the normalized object with their original text and no warning.
    if not use_exact:
        warnings = [
            w for w in warnings
            if w["code"] in (
                "ambiguous_table_classification",
                "missing_gene_symbol",
                "table_coverage",
                "conflicting_genotype",
            )
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "symbol": symbol,
        "source_file": source_file,
        "group": group_name,
        "use_exact_matcher": use_exact,
        "reference_tables": reference,
        "drug_recommendations": drugs,
        "review_tables": review,
        "bullets": bullets,
        "variants": variants,
        "preserved_pharmacogenomics": preserved_pgx,
        "warnings": warnings,
        "errors": errors,
    }


def _warn_conflicts(reference: list[dict], warnings: list) -> None:
    seen: dict[tuple, dict] = {}
    for record in reference:
        if record.get("role") != "genotype_phenotype":
            continue
        cell = record.get("genotype") or {}
        for token in cell.get("tokens") or []:
            key = (token.get("kind"), tuple(token.get("key") or []))
            label = strip_md(record.get("phenotype_raw", ""))
            prev = seen.get(key)
            if prev is None:
                seen[key] = record
                continue
            prev_label = strip_md(prev.get("phenotype_raw", ""))
            if prev_label != label:
                _warn(
                    warnings,
                    "conflicting_genotype",
                    f"{token.get('raw')} is mapped to both {prev_label!r} and {label!r}.",
                    record["provenance"],
                )


def _warn_drug_reference_gaps(reference: list[dict], drugs: list[dict], bullets: list[dict], warnings: list) -> None:
    reference_keys = set()
    for record in reference:
        if record.get("role") != "genotype_phenotype":
            continue
        cell = record.get("genotype") or {}
        for token in cell.get("tokens") or []:
            reference_keys.add((token.get("kind"), tuple(token.get("key") or [])))
        for alias in cell.get("aliases") or []:
            reference_keys.add((alias.get("kind"), tuple(alias.get("key") or [])))

    bullet_keys = set()
    genotype_bullets = 0
    for bullet in bullets:
        if bullet["scope"] != "genotype":
            continue
        genotype_bullets += 1
        for token in (bullet.get("genotype") or {}).get("tokens") or []:
            bullet_keys.add((token.get("kind"), tuple(token.get("key") or [])))

    if genotype_bullets:
        for record in reference:
            if record.get("role") != "genotype_phenotype":
                continue
            for token in (record.get("genotype") or {}).get("tokens") or []:
                key = (token.get("kind"), tuple(token.get("key") or []))
                if key not in bullet_keys:
                    _warn(
                        warnings,
                        "genotype_absent_from_bullets",
                        f"{token.get('raw')} is in the genotype table but in no genotype-scoped bullet.",
                        record["provenance"],
                    )

    for record in drugs:
        cell = record.get("genotype") or {}
        if cell.get("scope") == "variant":
            _warn(
                warnings,
                "drug_variant_not_a_diplotype",
                f"Drug row {record.get('drug_raw')} cites variant ids ({cell.get('text')}) and no genotype from the reference table.",
                record["provenance"],
            )
            continue
        if cell.get("scope") != "genotype":
            continue
        for token in cell.get("tokens") or []:
            key = (token.get("kind"), tuple(token.get("key") or []))
            if key not in reference_keys:
                _warn(
                    warnings,
                    "drug_genotype_not_in_reference",
                    f"Drug row genotype {token.get('raw')} ({strip_md(record.get('drug_raw', ''))}) is not a genotype reference row.",
                    record["provenance"],
                )


def ensure_gene(gene: dict, source_file: str = "", group_name: str = "") -> dict:
    existing = gene.get("normalization")
    if isinstance(existing, dict) and existing.get("schema_version") == SCHEMA_VERSION:
        return gene
    gene["normalization"] = build_normalization(gene, source_file, group_name)
    return gene


def normalize_knowledge_base(groups: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    warnings: list[dict] = []
    errors: list[dict] = []
    for group in groups:
        source_file = group.get("file", "")
        group_name = group.get("group", "")
        for gene in group.get("genes") or []:
            gene.pop("normalization", None)
            ensure_gene(gene, source_file, group_name)
            warnings.extend(gene["normalization"]["warnings"])
            errors.extend(gene["normalization"]["errors"])
        group["normalization_schema"] = SCHEMA_VERSION
    return groups, warnings, errors
