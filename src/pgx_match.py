"""Exact genotype matching for genes normalized with schema 1.

A gene uses this path only when ``normalization["use_exact_matcher"]`` is
true. Copy-number suffixes are compared as part of the allele. Star
diplotype order (``*1/*2`` versus ``*2/*1``) is an explicit equivalence.
A parenthetical alias is an equivalence only when that alias is written in
the source cell. Phenotype codes are taken from the matched reference row,
not inferred from a drug name or from a similar word.

``KNOWN_VARIANTS`` in ``interpreter.py`` is unchanged. This module consults
it only as a nucleotide fallback when the patient text has no explicit
genotype and the resulting nucleotide is itself a reference token.
"""

from __future__ import annotations

import re
from typing import Optional

from pgx_normalize import (
    STAR_IN_TEXT,
    parse_521_alias,
    parse_nucleotide_token,
    parse_star_allele_token,
    parse_star_diplotype,
    strip_md,
)

SINGLE_STAR = re.compile(r"(?<![\w*])(\*\d+[A-Za-z]*)(?![\w/])")

NUCLEOTIDE_WORD = re.compile(r"(?<![A-Za-z])([ACGT]{2})(?![A-Za-z])", re.IGNORECASE)
RSID_WORD = re.compile(r"rs\d+", re.IGNORECASE)
PAREN_BLOCK = re.compile(r"\([^)]*\)")


def _key(token: dict) -> tuple:
    return (token.get("kind"), tuple(token.get("key") or []))


def _same(a: dict, b: dict) -> bool:
    return _key(a) == _key(b)


def _find_explicit(text: str) -> list[dict]:
    """Pull genotypes that are written in the patient result."""
    found: list[dict] = []
    consumed = text
    for match in re.finditer(r"521\s*[ACGT]{2}", text, re.IGNORECASE):
        alias = parse_521_alias(match.group(0))
        if alias:
            found.append(alias)
            consumed = consumed.replace(match.group(0), " ")
    for match in STAR_IN_TEXT.finditer(consumed):
        token = parse_star_diplotype(match.group(0))
        if token:
            found.append(token)
            consumed = consumed.replace(match.group(0), " ", 1)
    for match in SINGLE_STAR.finditer(consumed):
        token = parse_star_allele_token(match.group(1))
        if token:
            found.append(token)
    # Nucleotide pairs that are not the trailing pair inside an already
    # consumed 521-alias.
    for match in NUCLEOTIDE_WORD.finditer(consumed):
        token = parse_nucleotide_token(match.group(1))
        if token:
            found.append(token)
    return found


def _unique_observations(tokens: list[dict]) -> list[dict]:
    unique = []
    seen = set()
    for token in tokens:
        if _key(token) in seen:
            continue
        seen.add(_key(token))
        unique.append(token)
    return unique


def _known_variant_nucleotides(result: str) -> list[dict]:
    from interpreter import extract_genotype_candidates

    tokens = []
    for candidate in extract_genotype_candidates(result):
        parsed = parse_nucleotide_token(candidate) or parse_star_diplotype(candidate)
        if parsed is not None and parsed["kind"] == "nucleotide":
            tokens.append(parsed)
    return _unique_observations(tokens)


def observe_patient(result: str) -> dict:
    text = result or ""
    # Drop prose parentheticals. Keep a parenthetical that itself contains a
    # star diplotype or a 521-alias; those are notations, not comments.
    def _keep(match: re.Match) -> str:
        inner = match.group(0)
        if STAR_IN_TEXT.search(inner) or re.search(r"521\s*[ACGT]{2}", inner, re.IGNORECASE):
            return inner
        return " "

    stripped = PAREN_BLOCK.sub(_keep, text)
    explicit = _unique_observations(_find_explicit(stripped))
    rsids = [m.group(0) for m in RSID_WORD.finditer(text)]
    return {"explicit": explicit, "rsids": rsids, "text": text}


def _reference_rows(norm: dict) -> list[dict]:
    return [r for r in norm.get("reference_tables") or [] if r.get("role") == "genotype_phenotype"]


def _notation(token: dict) -> str:
    return re.sub(r"\s+", "", token.get("raw") or "").lower()


def _row_matches_token(row: dict, observed: dict) -> Optional[str]:
    cell = row.get("genotype") or {}
    for token in cell.get("tokens") or []:
        if not _same(token, observed):
            continue
        if _notation(token) == _notation(observed):
            return "exact"
        if token.get("kind") == "nucleotide":
            return "explicit_alias"
        return "equivalent_order"
    for alias in cell.get("aliases") or []:
        if not _same(alias, observed):
            continue
        if _notation(alias) == _notation(observed):
            return "exact"
        return "explicit_alias"
    return None


def _select_drug(record: dict, observed: dict, phenotype_codes: list[str], phenotype_ambiguous: bool) -> tuple[bool, str]:
    scope = record.get("scope")
    cell = record.get("genotype") or {}
    if scope == "all":
        return True, "scope_all_explicit"
    if scope == "none":
        return False, "scope_drug_only"
    if scope == "conditional":
        return False, "second_gene_not_evaluated"
    if scope == "variant":
        return False, "variant_not_diplotype"
    if scope == "unparsed":
        return False, "scope_unparsed"
    if scope == "genotype":
        quality = _row_matches_token({"genotype": cell}, observed)
        if quality:
            return True, quality
        return False, "genotype_mismatch"
    if scope == "phenotype":
        if phenotype_ambiguous:
            return False, "combined_phenotype_label"
        wanted = set(cell.get("phenotype_codes") or [])
        have = set(phenotype_codes or [])
        if wanted and have and wanted & have:
            return True, "phenotype_code"
        if not have:
            return False, "phenotype_not_in_reference"
        return False, "phenotype_mismatch"
    return False, "scope_unparsed"


def _select_bullet(bullet: dict, observed: dict) -> tuple[bool, str]:
    scope = bullet.get("scope")
    if scope == "gene":
        return True, "gene_level"
    if scope == "unresolved":
        return False, "unresolved_scope"
    if scope == "genotype":
        cell = bullet.get("genotype") or {}
        if _row_matches_token({"genotype": cell}, observed):
            return True, "exact_genotype"
        return False, "genotype_mismatch"
    return False, "unresolved_scope"


def _display_token(row: dict, observed: dict, quality: str) -> str:
    cell = row.get("genotype") or {}
    for token in cell.get("tokens") or []:
        if _same(token, observed):
            return token["raw"]
    if quality == "explicit_alias":
        for alias in cell.get("aliases") or []:
            if _same(alias, observed):
                return alias["raw"]
    return observed.get("raw") or ""


def _replace_genotype_cell(row: dict, column: str, display: str) -> dict:
    copied = dict(row)
    if column and column in copied:
        copied[column] = display
        return copied
    for key in list(copied):
        if key.strip().lower().startswith("генотип"):
            copied[key] = display
            break
    return copied


def _drug_public(record: dict, reason: str) -> dict:
    return {
        "drugs": list(record.get("drugs") or []),
        "drug_raw": record.get("drug_raw", ""),
        "genotype_raw": record.get("genotype_raw", ""),
        "recommendation_raw": record.get("recommendation_raw", ""),
        "source_raw": record.get("source_raw", ""),
        "scope": record.get("scope"),
        "match_reason": reason,
        "provenance": record.get("provenance"),
        "source_row": record.get("row"),
    }


def _bullet_public(bullet: dict, reason: str) -> dict:
    return {
        "text": bullet.get("text", ""),
        "raw": bullet.get("raw", ""),
        "scope": bullet.get("scope"),
        "reason": bullet.get("reason", ""),
        "match_reason": reason,
        "provenance": bullet.get("provenance"),
    }


def try_exact_interpretation(patient_gene: dict, gene: dict, group_name: str, pgx_result: dict) -> Optional[dict]:
    norm = gene.get("normalization") or {}
    if not norm.get("use_exact_matcher"):
        return None

    observed_info = observe_patient(patient_gene.get("result", ""))
    explicit = list(observed_info["explicit"])
    source = "explicit"
    if not explicit:
        fallback = _known_variant_nucleotides(patient_gene.get("result", ""))
        # Keep a nucleotide synthesized from KNOWN_VARIANTS only when that
        # exact nucleotide is a reference token. This does not create a
        # star diplotype.
        reference_keys = set()
        for row in _reference_rows(norm):
            cell = row.get("genotype") or {}
            for token in cell.get("tokens") or []:
                reference_keys.add(_key(token))
            for alias in cell.get("aliases") or []:
                reference_keys.add(_key(alias))
        fallback = [tok for tok in fallback if _key(tok) in reference_keys]
        if fallback:
            explicit = fallback
            source = "known_variant_map"

    base = {
        "gene": patient_gene.get("gene", norm.get("symbol", "")),
        "group": group_name,
        "patient_result": patient_gene.get("result", ""),
        "patient_comment": patient_gene.get("comment", ""),
        "parts": [patient_gene.get("result", "")],
        "extracted_candidates": [t.get("raw") for t in explicit],
        "has_genotype_table": True,
        "pgx_annotations": pgx_result.get("matches") or [],
        "pgx_no_match_info": pgx_result.get("no_match_info"),
        "normalization_schema": norm.get("schema_version"),
        "evaluated_genotype": patient_gene.get("result", ""),
        "match_quality": "unsupported",
        "phenotype_label": "",
        "phenotype_codes": [],
        "phenotype_resolution": "unsupported",
        "recommendations": [],
        "gene_recommendations": [],
        "drug_recommendations": [],
        "unresolved_recommendations": [],
        "excluded_recommendations": [],
        "review_warnings": list(norm.get("warnings") or []),
    }

    if len(explicit) > 1:
        base["status"] = "no_genotype_match"
        base["match_quality"] = "ambiguous"
        base["phenotype_resolution"] = "ambiguous"
        base["matched_genotype"] = None
        base["matches"] = []
        base["full_row"] = None
        base["note"] = "The result contains more than one genotype. No phenotype or recommendation was selected."
        return base

    if len(explicit) == 0:
        base["status"] = "no_genotype_match"
        base["matches"] = []
        base["full_row"] = None
        base["matched_genotype"] = None
        rsids = observed_info["rsids"]
        known = [v for v in norm.get("variants") or [] if v.get("rsid", "").lower() in {r.lower() for r in rsids}]
        if known:
            described = ", ".join(
                f"{v['rsid']} ({v['note']})" if v.get("note") else v["rsid"] for v in known
            )
            base["match_quality"] = "unresolved"
            base["phenotype_resolution"] = "unresolved"
            base["note"] = (
                f"Source identity table lists {described}, but the patient result does not state a diplotype. "
                "No phenotype was assigned."
            )
            base["unresolved_recommendations"] = [{
                "text": base["note"],
                "match_reason": "variant_without_diplotype",
                "provenance": known[0].get("provenance"),
            }]
        else:
            base["note"] = "Genotype is not in the reference table. No recommendation was selected."
        return base

    observed = explicit[0]
    hits = []
    for row in _reference_rows(norm):
        quality = _row_matches_token(row, observed)
        if quality:
            if source == "known_variant_map":
                quality = "known_variant_map"
            hits.append((row, quality))

    labels = {strip_md(row.get("phenotype_raw", "")) for row, _q in hits}
    if len(hits) > 1 and len(labels) > 1:
        base["status"] = "no_genotype_match"
        base["match_quality"] = "ambiguous"
        base["phenotype_resolution"] = "ambiguous"
        base["matched_genotype"] = observed.get("raw")
        base["matches"] = []
        base["full_row"] = None
        base["note"] = "This genotype is listed under more than one phenotype. No phenotype or recommendation was selected."
        base["ambiguous_sources"] = [row.get("provenance") for row, _q in hits]
        return base

    selected_bullets = []
    gene_bullets = []
    unresolved = []
    excluded = []
    for bullet in norm.get("bullets") or []:
        keep, reason = _select_bullet(bullet, observed)
        public = _bullet_public(bullet, reason)
        if keep and bullet.get("scope") == "gene":
            gene_bullets.append(public)
            selected_bullets.append(public)
        elif keep:
            selected_bullets.append(public)
        elif bullet.get("scope") == "unresolved":
            unresolved.append(public)
        else:
            excluded.append(public)

    selected_drugs = []
    phenotype_codes: list[str] = []
    phenotype_ambiguous = False
    if hits:
        row, quality = hits[0]
        phenotype_codes = list(row.get("phenotype_codes") or [])
        phenotype_ambiguous = bool(row.get("phenotype_codes_ambiguous"))
        display = _display_token(row, observed, quality)
        full = _replace_genotype_cell(row.get("row") or {}, row.get("genotype_column") or "", display)
        base["status"] = "matched"
        base["match_quality"] = quality
        base["matched_genotype"] = display
        base["normalized_genotype"] = {
            "raw": observed.get("raw"),
            "normalized": observed.get("normalized"),
            "kind": observed.get("kind"),
            "alleles": observed.get("alleles"),
            "key": observed.get("key"),
            "source": source,
        }
        base["phenotype_label"] = row.get("phenotype_raw", "")
        base["phenotype_codes"] = phenotype_codes
        base["phenotype_resolution"] = "combined_label" if phenotype_ambiguous else "explicit" if phenotype_codes or row.get("phenotype_raw") else "unlabeled"
        base["matches"] = [{
            "genotype": display,
            "full_row": full,
            "source_part": patient_gene.get("result", ""),
            "match_quality": quality,
            "provenance": row.get("provenance"),
        }]
        base["full_row"] = full
        base["recommendations"] = [b["text"] for b in selected_bullets]
        base["gene_recommendations"] = [b["text"] for b in gene_bullets]
        if phenotype_ambiguous:
            base["note"] = (
                "The reference row lists this genotype under a combined phenotype label. "
                "Phenotype-specific drug rows were not applied."
            )
    else:
        quality = "exact" if source == "explicit" else source
        base["match_quality"] = "unsupported" if source == "explicit" else source
        base["phenotype_resolution"] = "not_in_reference_table"
        base["matched_genotype"] = observed.get("raw")
        base["normalized_genotype"] = {
            "raw": observed.get("raw"),
            "normalized": observed.get("normalized"),
            "kind": observed.get("kind"),
            "alleles": observed.get("alleles"),
            "key": observed.get("key"),
            "source": source,
        }
        base["matches"] = []
        base["full_row"] = None
        base["recommendations"] = [b["text"] for b in selected_bullets]
        base["gene_recommendations"] = [b["text"] for b in gene_bullets]
        base["note"] = "Genotype is not in the phenotype reference table. Phenotype was not assigned."
        # Drug rows can still match an explicit genotype token.
        phenotype_codes = []
        phenotype_ambiguous = False
        quality = "exact"

    for record in norm.get("drug_recommendations") or []:
        keep, reason = _select_drug(record, observed, phenotype_codes, phenotype_ambiguous if hits else False)
        public = _drug_public(record, reason)
        if keep:
            selected_drugs.append(public)
        else:
            excluded.append({
                "drug_raw": record.get("drug_raw", ""),
                "genotype_raw": record.get("genotype_raw", ""),
                "recommendation_raw": record.get("recommendation_raw", ""),
                "match_reason": reason,
                "provenance": record.get("provenance"),
            })

    # Re-run phenotype exclusion with the resolved flags when we have a hit.
    # The loop above used the right flags. For the no-hit path, phenotype
    # scope stays excluded via empty phenotype codes.

    base["drug_recommendations"] = selected_drugs
    base["unresolved_recommendations"] = unresolved
    base["excluded_recommendations"] = excluded

    if hits:
        return base

    if selected_drugs:
        base["status"] = "matched"
        base["match_quality"] = "exact"
        base["phenotype_resolution"] = "not_in_reference_table"
        return base

    base["status"] = "no_genotype_match"
    base["matched_genotype"] = None
    return base
