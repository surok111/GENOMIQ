"""
Интерпретатор генетических анализов (v13).

Ключевое отличие v13 от v12:
- Фармакогенетика теперь возвращает ТОЛЬКО аннотации, релевантные пациенту.
- Если совпадений нет — возвращается честная справка "нет данных для генотипа X".
- Ассоциации чистятся от служебных маркеров ClinPGx (More Details, Note и т.д.).

Логика матчинга:
- "exact"  — генотип пациента полностью совпал (CC, CT, TT, AG+GG)
- "allele" — у пациента есть аллель, упомянутый в аннотации (Allele A, Allele G)

Результаты:
- patient_report.json
- patient_report.md
"""

import json
import os
import re
from pathlib import Path
from typing import Optional


BASE_PATH = "parsed_knowledge_base_clean.json"
SAMPLES_DIR = "samples"
OUT_JSON = "patient_report.json"
OUT_MD = "patient_report.md"


NORMAL_PHRASES = [
    'не обнаружено', 'не выявлено', 'норма', 'нормально',
    'дикий тип', 'wild type', 'без мутаций', 'не носитель',
]


NON_GENOTYPE_COLUMNS = {
    'вариант', 'лекарство', 'эффект', 'уровень',
    'препарат', 'guidance', 'источник', 'домен',
    'rsid', 'изоформа',
}


KNOWN_VARIANTS = {
    'лейден': ('C', 'T'),
    'g20210a': ('G', 'A'),
    'rs1799963': ('G', 'A'),
    'rs6025': ('C', 'T'),
    's447x': ('C', 'G'),
    'rs328': ('C', 'G'),
    'r46l': ('G', 'T'),
    'rs11591147': ('G', 'T'),
    'e670g': ('A', 'G'),
    'rs505151': ('A', 'G'),
    'rs429358': ('T', 'C'),
    'rs7412': ('C', 'T'),
    'c677t': ('C', 'T'),
    'a1298c': ('A', 'C'),
    'a2756g': ('A', 'G'),
    'a66g': ('A', 'G'),
    'y328c': ('A', 'G'),
    '844ins68': ('ins', 'ins'),
    'rs1799853': ('C', 'T'),
    'rs1057910': ('A', 'C'),
    'rs4244285': ('G', 'A'),
    'rs4986893': ('G', 'A'),
    'rs12248560': ('C', 'T'),
    'rs762551': ('C', 'A'),
    'rs4149056': ('T', 'C'),
    'r577x': ('C', 'T'),
    'rs1815739': ('C', 'T'),
    '-13910c>t': ('C', 'T'),
    'rs4988235': ('C', 'T'),
    'val158met': ('G', 'A'),
    'rs4680': ('G', 'A'),
    'rs9939609': ('T', 'A'),
    'pro12ala': ('C', 'G'),
    'rs1801282': ('C', 'G'),
    'ile462val': ('A', 'G'),
    'rs1048943': ('A', 'G'),
    'ile105val': ('A', 'G'),
    'rs1695': ('A', 'G'),
    'pro72arg': ('C', 'G'),
    'rs1042522': ('C', 'G'),
    'pro47ser': ('C', 'T'),
    'rs28934578': ('G', 'A'),
    'rs11540652': ('G', 'A'),
    'g590a': ('G', 'A'),
    'rs1799930': ('G', 'A'),
    'g857a': ('G', 'A'),
    'rs1799931': ('G', 'A'),
    'c481t': ('C', 'T'),
    'rs1799929': ('C', 'T'),
    'a803g': ('A', 'G'),
    'rs1208': ('A', 'G'),
    'rs1544410': ('C', 'T'),
    'rs2228570': ('C', 'T'),
    'rs7975232': ('A', 'C'),
    'rs731236': ('T', 'C'),
    'rs1800629': ('G', 'A'),
    'rs1800795': ('G', 'C'),
    'rs1800566': ('C', 'T'),
    'rs4880': ('C', 'T'),
    'rs1001179': ('C', 'T'),
    'rs1799945': ('C', 'G'),
    'rs1800562': ('G', 'A'),
    'rs492602': ('G', 'A'),
}


# ============================================================
#  Загрузка базы знаний
# ============================================================

def load_base(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_gene_name(header: str) -> str:
    m = re.match(r'^([A-Z0-9/ ]+?)\s*[—\-–]', header)
    if m:
        return m.group(1).strip()
    return header.split()[0] if header.split() else header


def build_gene_index(base: list[dict]) -> dict:
    index = {}
    for group in base:
        for gene in group["genes"]:
            name = extract_gene_name(gene["header"])
            index[name.upper()] = (group["group"], gene)
    return index


def _strip_md(s: str) -> str:
    if not s:
        return s
    return re.sub(r'\*\*(.+?)\*\*', r'\1', str(s)).strip()


# ============================================================
#  Чтение отчёта пациента
# ============================================================

RE_GENE = re.compile(r'^\s*Ген\s*:\s*(.+?)\s*$', re.IGNORECASE)
RE_RESULT = re.compile(r'^\s*Результат\s*:\s*(.+?)\s*$', re.IGNORECASE)
RE_COMMENT = re.compile(r'^\s*Комментарий\s*:\s*(.+?)\s*$', re.IGNORECASE)


def parse_patient_report(text: str) -> list[dict]:
    patients = []
    current = None
    last_field = None

    for raw_line in text.split('\n'):
        line = raw_line.strip()

        if not line or set(line) <= set('=-'):
            last_field = None
            continue

        m = RE_GENE.match(line)
        if m:
            if current:
                patients.append(current)
            current = {"gene": m.group(1).strip(), "result": "", "comment": ""}
            last_field = "gene"
            continue

        if current is None:
            continue

        m = RE_RESULT.match(line)
        if m:
            current["result"] = m.group(1).strip()
            last_field = "result"
            continue

        m = RE_COMMENT.match(line)
        if m:
            current["comment"] = m.group(1).strip()
            last_field = "comment"
            continue

        if last_field == "result":
            current["result"] += " " + line
        elif last_field == "comment":
            current["comment"] += " " + line

    if current:
        patients.append(current)
    return patients


def read_txt(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def read_any(path: str) -> str:
    if path.lower().endswith(".docx"):
        return read_docx(path)
    return read_txt(path)


# ============================================================
#  Извлечение генотипов пациента
# ============================================================

def _normalize(gt: str) -> str:
    if not gt:
        return ""
    s = gt.strip()
    s = re.sub(r'\s*\(.*?\)', '', s)
    s = s.strip()
    if s.startswith('*'):
        return s.replace(' ', '').lower()
    s = s.replace('/', '').replace(' ', '').replace('|', '').lower()
    if len(s) == 2 and all(c in 'acgt' for c in s):
        return ''.join(sorted(s))
    return s


def _is_normal(result: str) -> bool:
    low = result.lower()
    return any(k in low for k in NORMAL_PHRASES)


def _is_het(text: str) -> bool:
    return 'гетерозигот' in text.lower()


def _is_hom(text: str) -> bool:
    return 'гомозигот' in text.lower()


RE_VARIANT = re.compile(
    r'(?<![A-Za-z])[cC]?\.?-?\d*[ACGT]>[ACGT]'
    r'|(?<![A-Za-z])[ACGT]\d+[ACGT](?![A-Za-z])'
    r'|(?<![A-Za-z])-?\d+[ACGT]>[ACGT](?![A-Za-z])'
)

RE_PAIR_NUC = re.compile(r'(?<![A-Za-z])([ACGT]{2})(?![A-Za-z])')
RE_PAIR_ANY = re.compile(r'(?<![A-Za-z])([A-Z]{2})(?![A-Za-z])')
RE_STAR = re.compile(r'(\*\d+/\*\d+)')
RE_APOE_ISOFORM = re.compile(r'\bE([234])/E([234])\b', re.IGNORECASE)


def _extract_variant_alleles(variant: str) -> tuple[str, str]:
    v = variant.replace('c.', '').replace('C.', '')
    if '>' in v:
        parts = v.split('>')
        ref = re.findall(r'[ACGT]', parts[0])[-1] if parts[0] else ''
        mut = re.findall(r'[ACGT]', parts[1])[0] if parts[1] else ''
        return ref, mut
    letters = re.findall(r'[ACGT]', v)
    if len(letters) >= 2:
        return letters[0], letters[-1]
    return '', ''


def extract_genotype_candidates(result: str) -> list[str]:
    r = result.strip()
    if not r:
        return []
    if _is_normal(r):
        return []

    candidates = []
    seen = set()

    def add(c: str):
        if c and c not in seen:
            seen.add(c)
            candidates.append(c)

    het = _is_het(r)
    hom = _is_hom(r)

    tmp = r
    for m in RE_VARIANT.finditer(r):
        tmp = tmp.replace(m.group(0), ' ', 1)

    explicit_pairs = []
    for m in RE_PAIR_NUC.finditer(tmp):
        explicit_pairs.append(m.group(1))

    if explicit_pairs:
        for gt in explicit_pairs:
            add(gt)
        return candidates

    for m in RE_STAR.finditer(r):
        add(m.group(1))

    for m in re.finditer(r'([A-Za-zА-Яа-я0-9*]+(?:/[A-Za-zА-Яа-я0-9*]+)+)', r):
        val = m.group(1)
        if len(val) <= 12:
            add(val)

    r_low = r.lower()
    for name, (ref, mut) in KNOWN_VARIANTS.items():
        if name in r_low:
            if het:
                add(ref + mut)
                add(mut + ref)
            elif hom:
                add(mut + mut)
            else:
                add(mut + mut)
                add(ref + mut)
            break

    if not candidates:
        for m in RE_VARIANT.finditer(r):
            ref, mut = _extract_variant_alleles(m.group(0))
            if not ref or not mut:
                continue
            if het:
                add(ref + mut)
                add(mut + ref)
            elif hom:
                add(mut + mut)
            else:
                add(mut + mut)
                add(ref + mut)

    if het or hom:
        for m in RE_PAIR_ANY.finditer(r):
            add(m.group(1))

    m = re.search(r'\b([a-z]{2})\b', r)
    if m and (het or hom):
        add(m.group(1))

    return candidates


# ============================================================
#  Поиск совпадений в таблицах генотипов
# ============================================================

GENOTYPE_COLUMN_NAMES = {'генотип', 'аллели', 'alleles', 'genotype'}


def _is_genotype_column(h: str) -> bool:
    hl = h.strip().lower()
    if hl in GENOTYPE_COLUMN_NAMES:
        return True
    if hl.startswith('генотип'):
        return True
    return False


def _is_gene_table(headers: list[str]) -> bool:
    has_gt = any(_is_genotype_column(h) for h in headers)
    has_drug = any(h.strip().lower() in NON_GENOTYPE_COLUMNS for h in headers)
    return has_gt and not has_drug


def has_real_genotype_table(gene: dict) -> bool:
    for sec in gene["sections"]:
        for tbl in sec["tables"]:
            if _is_gene_table(tbl.get("headers", [])):
                return True
    return False


def _is_star_overlap(cn: str, row_norm: str) -> bool:
    if not (cn.startswith('*') or row_norm.startswith('*')):
        return False
    if cn not in row_norm and row_norm not in cn:
        return False
    if 'xn' in row_norm or 'x2' in row_norm or 'x3' in row_norm:
        if 'xn' not in cn and 'x2' not in cn and 'x3' not in cn:
            return False
    return True


def find_genotype_rows_for_candidates(gene: dict, candidates: list[str]) -> list[dict]:
    if not candidates:
        return []
    cand_norm = [(c, _normalize(c)) for c in candidates if _normalize(c)]
    if not cand_norm:
        return []

    GT_COLUMNS = {'генотип', 'аллели', 'alleles', 'genotype'}

    def is_gt_col(h: str) -> bool:
        hl = h.strip().lower()
        return hl in GT_COLUMNS or hl.startswith('генотип') or hl.startswith('аллели')

    matches = []
    seen_rows = set()

    for sec in gene["sections"]:
        for tbl in sec["tables"]:
            headers = tbl.get("headers", [])
            if not _is_gene_table(headers):
                continue
            gt_cols = [h for h in headers if is_gt_col(h)]
            if not gt_cols:
                continue

            for row in tbl["rows"]:
                row_key = tuple(sorted((k, str(v)) for k, v in row.items() if v))
                best_match = None

                for gt_col in gt_cols:
                    row_gt = row.get(gt_col, "").strip()
                    if not row_gt:
                        continue
                    row_norm = _normalize(row_gt)
                    for orig, cn in cand_norm:
                        matched = False
                        if cn == row_norm:
                            matched = True
                        elif cn.replace('/', '') == row_norm.replace('/', ''):
                            matched = True
                        elif _is_star_overlap(cn, row_norm):
                            matched = True
                        if matched:
                            best_match = (row_gt, orig, gt_col)
                            break
                    if best_match:
                        break

                if not best_match:
                    continue
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)

                row_gt, orig, gt_col = best_match
                matches.append({
                    "section": sec,
                    "table": tbl,
                    "row": row,
                    "matched_field": row_gt,
                    "matched_candidate": orig,
                    "matched_column": gt_col,
                })

    return matches


def _find_wild_type_row(gene: dict) -> Optional[dict]:
    for sec in gene["sections"]:
        for tbl in sec["tables"]:
            headers = tbl.get("headers", [])
            if not _is_gene_table(headers):
                continue
            gt_col = None
            for h in headers:
                if _is_genotype_column(h):
                    gt_col = h
                    break
            if gt_col is None:
                continue
            for row in tbl["rows"]:
                row_gt = row.get(gt_col, "").strip()
                if not row_gt:
                    continue
                clean = _strip_md(re.sub(r'\s*\(.*?\)', '', row_gt))
                clean = clean.replace('/', '').strip()
                if len(clean) == 2 and clean[0] == clean[1] and clean[0] in 'ACGT':
                    return {
                        "section": sec, "table": tbl, "row": row,
                        "matched_field": _strip_md(row_gt),
                        "matched_candidate": "норма",
                    }
    for sec in gene["sections"]:
        for tbl in sec["tables"]:
            headers = tbl.get("headers", [])
            if not _is_gene_table(headers):
                continue
            gt_col = None
            for h in headers:
                if _is_genotype_column(h):
                    gt_col = h
                    break
            if gt_col is None:
                continue
            for row in tbl["rows"]:
                row_gt = row.get(gt_col, "").strip()
                if 'норм' in row_gt.lower() or 'дикий' in row_gt.lower():
                    return {
                        "section": sec, "table": tbl, "row": row,
                        "matched_field": _strip_md(row_gt),
                        "matched_candidate": "норма",
                    }
    return None


# ============================================================
#  ФАРМАКОГЕНЕТИКА (v13) — только релевантное
# ============================================================

def _extract_patient_alleles(result: str) -> set:
    """Возвращает множество аллелей/генотипов пациента."""
    if not result:
        return set()
    text = result.upper()
    alleles = set()

    for m in re.finditer(r'(\*\d+/\*\d+)', text):
        alleles.add(m.group(1))

    for m in re.finditer(r'(?<![A-Z])([ACGT]{2})(?![A-Z])', text):
        gt = m.group(1)
        alleles.add(gt)
        if len(gt) == 2 and gt[0] != gt[1]:
            alleles.add(gt[::-1])

    for m in re.finditer(r'(?:аллель|allele|носител)\w*\s+([ACGT])(?![A-Z])', text, re.IGNORECASE):
        alleles.add(m.group(1))

    for m in re.finditer(r'(?<![A-Za-z])([a-z]{2})(?![A-Za-z])', result):
        alleles.add(m.group(1).upper())

    return alleles


def _parse_pvalue(p: str) -> float:
    if not p:
        return 999
    s = str(p).strip().lstrip('=').lstrip('<').lstrip('>').strip()
    try:
        return float(s)
    except ValueError:
        return 999


def _clean_assoc(assoc: str) -> str:
    """Обрезает сырой текст ассоциации ClinPGx."""
    if not assoc:
        return ""
    text = assoc

    cut_markers = [
        'More Details:', 'Note:', 'Alleles complemented',
        'Please note', 'Alleles have been', 'Alleles given',
    ]
    for marker in cut_markers:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]

    text = text.strip()
    text = re.sub(r'\s{2,}', ' ', text)

    if len(text) > 300:
        text = text[:297].rstrip() + "…"

    return text


def _extract_genotypes_from_association(assoc: str) -> list[str]:
    """Извлекает генотипы, упомянутые в тексте Association."""
    if not assoc:
        return []

    text = assoc

    m = re.search(r'Genotypes?\s+([A-Z]{1,3}(?:\s*\+\s*[A-Z]{1,3})+)', text)
    if m:
        return [g.strip() for g in m.group(1).split('+') if g.strip()]

    m = re.search(r'Genotypes?\s+([A-Z]{1,3})\b', text)
    if m:
        g = m.group(1).strip()
        if g and g not in ('—', '-'):
            return [g]

    m = re.search(r'Allele\s+([A-Z])\b', text)
    if m:
        return [m.group(1)]

    m = re.search(r'"([A-Z]{2})"', text)
    if m:
        return [m.group(1)]

    return []


def find_pgx_annotations(gene: dict, patient_alleles: set, top_n: int = 50) -> dict:
    """
    Возвращает только аннотации, релевантные пациенту.

    {
      "matches": [...],       # совпавшие (exact / allele)
      "no_match_info": {...}  # если совпадений нет — статистика по базе
    }
    """
    all_matches = []

    for sec in gene.get("sections", []):
        for tbl in sec.get("pharmacogenomics", []):
            for row in tbl.get("rows", []):
                sig = str(row.get("Sig", "")).strip().lower()
                if sig and sig not in ("yes", "not stated", "—", ""):
                    continue

                assoc = row.get("Association", "").strip()
                if not assoc:
                    continue

                drug = row.get("Drug", "").strip()
                pval = row.get("P-value", "").strip()
                pheno = row.get("Phenotype", "").strip()
                variant = row.get("Variant", "").strip()

                assoc_genotypes = _extract_genotypes_from_association(assoc)
                patient_norm = {a.upper().replace('/', '') for a in patient_alleles}

                matched_genotypes = []
                match_kind = None
                is_matched = False

                for g in assoc_genotypes:
                    g_norm = g.upper().replace('/', '')

                    # 1) точный генотип
                    if len(g_norm) == 2 and g_norm in patient_norm:
                        is_matched = True
                        match_kind = 'exact'
                        matched_genotypes.append(g)
                        continue

                    if len(g_norm) == 2:
                        for p in patient_norm:
                            if len(p) == 2 and (p == g_norm or p == g_norm[::-1]):
                                is_matched = True
                                match_kind = match_kind or 'exact'
                                matched_genotypes.append(g)
                                break

                    # 2) одиночный аллель
                    if len(g_norm) == 1:
                        for p in patient_norm:
                            if len(p) == 2 and g_norm in p:
                                is_matched = True
                                match_kind = match_kind or 'allele'
                                matched_genotypes.append(g)

                if not is_matched:
                    continue

                cleaned_assoc = _clean_assoc(assoc)

                all_matches.append({
                    "variant": variant,
                    "drug": drug or "—",
                    "association": cleaned_assoc,
                    "association_raw": assoc,
                    "pvalue": pval or "—",
                    "pvalue_num": _parse_pvalue(pval),
                    "phenotype": pheno or "Other",
                    "assoc_genotypes": assoc_genotypes,
                    "matched_genotypes": matched_genotypes,
                    "match_kind": match_kind,
                    "section": sec.get("code", "") + " " + sec.get("title", ""),
                })

    # дедупликация
    seen = set()
    unique = []
    for m in all_matches:
        key = (m["drug"], m["association"][:100])
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)

    # сортировка: exact сверху, потом по P-value
    unique.sort(key=lambda x: (0 if x["match_kind"] == "exact" else 1, x["pvalue_num"]))
    matches = unique[:top_n]

    # нет совпадений — собираем статистику по базе
    no_match_info = None
    if not matches:
        all_genotypes_in_base = set()
        total_annotations = 0
        for sec in gene.get("sections", []):
            for tbl in sec.get("pharmacogenomics", []):
                for row in tbl.get("rows", []):
                    sig = str(row.get("Sig", "")).strip().lower()
                    if sig and sig not in ("yes", "not stated", "—", ""):
                        continue
                    if not row.get("Association", "").strip():
                        continue
                    total_annotations += 1
                    for g in _extract_genotypes_from_association(row["Association"]):
                        all_genotypes_in_base.add(g.upper())

        no_match_info = {
            "total_annotations": total_annotations,
            "genotypes_in_base": sorted(all_genotypes_in_base),
            "patient_genotypes": sorted({a.upper() for a in patient_alleles if len(a) <= 3}),
        }

    return {
        "matches": matches,
        "no_match_info": no_match_info,
    }


# ============================================================
#  Разбиение результата
# ============================================================

def split_result_into_parts(result: str) -> list[str]:
    parts = re.split(r',\s*(?=(?:[A-Za-z]{1,3}[\d\.]*[A-Za-z]|rs\d|\*))', result)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if len(parts) > 1 else [result.strip()]


# ============================================================
#  Интерпретация гена
# ============================================================

def _collect_recommendations(gene: dict) -> list[str]:
    recs = []
    for sec in gene["sections"]:
        recs.extend(sec.get("bullets", []))
    return recs


def _try_deletion_genes(raw_name, patient_gene, gene, group_name, pgx_result):
    if raw_name.upper() not in ('GSTM1', 'GSTT1'):
        return None
    res_low = patient_gene["result"].lower()
    if not ('норма' in res_low or 'non-null' in res_low):
        return None

    recommendations = _collect_recommendations(gene)
    for sec in gene["sections"]:
        for tbl in sec["tables"]:
            headers = tbl.get("headers", [])
            if not _is_gene_table(headers):
                continue
            gt_col = None
            for h in headers:
                if _is_genotype_column(h):
                    gt_col = h
                    break
            if gt_col is None:
                continue
            for row in tbl["rows"]:
                row_gt = row.get(gt_col, "").strip()
                if 'non-null' in row_gt.lower():
                    return {
                        "gene": raw_name, "group": group_name,
                        "patient_result": patient_gene["result"],
                        "patient_comment": patient_gene.get("comment", ""),
                        "parts": [patient_gene["result"]],
                        "extracted_candidates": ["non-null / non-null"],
                        "has_genotype_table": True,
                        "recommendations": recommendations,
                        "status": "matched",
                        "matches": [{
                            "genotype": _strip_md(row_gt),
                            "full_row": row,
                            "source_part": "норма (non-null)",
                        }],
                        "matched_genotype": _strip_md(row_gt),
                        "full_row": row,
                        "pgx_annotations": pgx_result["matches"],
                        "pgx_no_match_info": pgx_result["no_match_info"],
                    }
    return None


def _try_apoe_isoform(raw_name, patient_gene, gene, group_name, pgx_result):
    if raw_name.upper() != 'APOE':
        return None
    result = patient_gene["result"].strip()
    m = RE_APOE_ISOFORM.search(result)
    if not m:
        return None
    isoform_str = m.group(0).upper().replace(' ', '')
    recommendations = _collect_recommendations(gene)
    for sec in gene["sections"]:
        for tbl in sec["tables"]:
            for row in tbl["rows"]:
                for col_name, cell_val in row.items():
                    if not cell_val:
                        continue
                    cell_clean = _strip_md(str(cell_val)).upper().replace(' ', '')
                    if isoform_str in cell_clean:
                        clean_isoform = _strip_md(row.get("Изоформа", isoform_str))
                        return {
                            "gene": raw_name, "group": group_name,
                            "patient_result": patient_gene["result"],
                            "patient_comment": patient_gene.get("comment", ""),
                            "parts": [patient_gene["result"]],
                            "extracted_candidates": [isoform_str],
                            "has_genotype_table": True,
                            "recommendations": recommendations,
                            "status": "matched",
                            "matches": [{
                                "genotype": clean_isoform,
                                "full_row": row,
                                "source_part": patient_gene["result"],
                            }],
                            "matched_genotype": clean_isoform,
                            "full_row": row,
                            "pgx_annotations": pgx_result["matches"],
                            "pgx_no_match_info": pgx_result["no_match_info"],
                        }
    return None


def interpret_gene(patient_gene: dict, gene_index: dict) -> dict:
    raw_name = patient_gene["gene"].strip()
    name_upper = raw_name.upper()

    base_entry = gene_index.get(name_upper)
    if base_entry is None:
        for key, entry in gene_index.items():
            if name_upper in key or key in name_upper:
                base_entry = entry
                break

    if base_entry is None:
        return {
            "gene": raw_name,
            "patient_result": patient_gene["result"],
            "patient_comment": patient_gene.get("comment", ""),
            "status": "not_in_knowledge_base",
            "matches": [],
            "pgx_annotations": [],
            "pgx_no_match_info": None,
        }

    group_name, gene = base_entry

    # Все аллели пациента
    patient_alleles = _extract_patient_alleles(patient_gene.get("result", ""))
    patient_alleles |= _extract_patient_alleles(patient_gene.get("comment", ""))

    # Один вызов pgx — используется во всех ветках
    pgx_result = find_pgx_annotations(gene, patient_alleles)

    # Специальные случаи
    special = _try_deletion_genes(raw_name, patient_gene, gene, group_name, pgx_result)
    if special is not None:
        return special

    apoe_special = _try_apoe_isoform(raw_name, patient_gene, gene, group_name, pgx_result)
    if apoe_special is not None:
        return apoe_special

    recommendations = _collect_recommendations(gene)
    has_table = has_real_genotype_table(gene)

    # "норма" → ищем wild type
    if _is_normal(patient_gene["result"]) and has_table:
        wild_row = _find_wild_type_row(gene)
        if wild_row:
            return {
                "gene": raw_name, "group": group_name,
                "patient_result": patient_gene["result"],
                "patient_comment": patient_gene.get("comment", ""),
                "parts": [patient_gene["result"]],
                "extracted_candidates": ["норма (дикий тип)"],
                "has_genotype_table": True,
                "recommendations": recommendations,
                "status": "matched",
                "matches": [{
                    "genotype": wild_row["matched_field"],
                    "full_row": wild_row["row"],
                    "source_part": patient_gene["result"],
                }],
                "matched_genotype": wild_row["matched_field"],
                "full_row": wild_row["row"],
                "pgx_annotations": pgx_result["matches"],
                "pgx_no_match_info": pgx_result["no_match_info"],
            }

    # Основной матчинг
    parts = split_result_into_parts(patient_gene["result"])
    all_matches = []
    all_candidates = []
    for part in parts:
        cands = extract_genotype_candidates(part)
        all_candidates.extend(cands)
        if has_table and cands:
            matches = find_genotype_rows_for_candidates(gene, cands)
            for m in matches:
                m["source_part"] = part
                all_matches.append(m)

    unique_matches = []
    seen_rows = set()
    for m in all_matches:
        row_key = tuple(sorted((k, str(v)) for k, v in m["row"].items() if v))
        if row_key in seen_rows:
            continue
        seen_rows.add(row_key)
        unique_matches.append(m)

    base_info = {
        "gene": raw_name, "group": group_name,
        "patient_result": patient_gene["result"],
        "patient_comment": patient_gene.get("comment", ""),
        "parts": parts,
        "extracted_candidates": all_candidates,
        "has_genotype_table": has_table,
        "recommendations": recommendations,
        "pgx_annotations": pgx_result["matches"],
        "pgx_no_match_info": pgx_result["no_match_info"],
    }

    if unique_matches:
        base_info["status"] = "matched"
        base_info["matches"] = [
            {"genotype": _strip_md(m["matched_field"]), "full_row": m["row"],
             "source_part": m.get("source_part", "")}
            for m in unique_matches
        ]
        base_info["matched_genotype"] = ", ".join(
            _strip_md(m["matched_field"]) for m in unique_matches
        )
        base_info["full_row"] = unique_matches[0]["row"]
    elif not has_table:
        base_info["status"] = "no_table_in_base"
        base_info["matches"] = []
        base_info["matched_genotype"] = None
        base_info["full_row"] = None
        base_info["note"] = (
            "В базе знаний нет таблицы генотипов для этого гена. "
            "Используйте комментарий пациента и общие рекомендации."
        )
    else:
        base_info["status"] = "no_genotype_match"
        base_info["matches"] = []
        base_info["matched_genotype"] = None
        base_info["full_row"] = None
        base_info["note"] = (
            "Генотип не удалось сопоставить с таблицей базы. Проверьте вручную."
        )

    return base_info


# ============================================================
#  Обработка файла
# ============================================================

def process_sample(path: str, gene_index: dict) -> dict:
    text = read_any(path)
    patients = parse_patient_report(text)
    results = [interpret_gene(p, gene_index) for p in patients]

    stats = {
        "matched": sum(1 for r in results if r["status"] == "matched"),
        "no_genotype_match": sum(1 for r in results if r["status"] == "no_genotype_match"),
        "no_table_in_base": sum(1 for r in results if r["status"] == "no_table_in_base"),
        "not_in_knowledge_base": sum(1 for r in results if r["status"] == "not_in_knowledge_base"),
    }

    return {
        "file": os.path.basename(path),
        "genes_total": len(results),
        "stats": stats,
        "results": results,
    }


# ============================================================
#  Вывод в консоль
# ============================================================

STATUS_ICON = {
    "matched": "✅",
    "no_genotype_match": "⚠️ ",
    "no_table_in_base": "🟡",
    "not_in_knowledge_base": "❌",
}


def _pick_risk(row: dict) -> str:
    for k, v in row.items():
        kl = k.lower()
        if 'риск' in kl or 'профиль' in kl or 'фенотип' in kl:
            return _strip_md(v)
    return ""


def print_sample_report(rep: dict):
    print("=" * 78)
    print(f"  ОТЧЁТ: {rep['file']}")
    print("=" * 78)
    s = rep["stats"]
    print(f"  Генов: {rep['genes_total']}  |  "
          f"✅ matched: {s['matched']}  |  "
          f"🟡 no_table: {s['no_table_in_base']}  |  "
          f"⚠️  no_match: {s['no_genotype_match']}  |  "
          f"❌ not_in_base: {s['not_in_knowledge_base']}")
    print()

    for r in rep["results"]:
        st = r["status"]
        icon = STATUS_ICON.get(st, "·")
        gene = r["gene"]
        pgx_count = len(r.get("pgx_annotations", []))
        pgx_no_match = r.get("pgx_no_match_info")

        if pgx_count:
            pgx_suffix = f"  💊×{pgx_count}"
        elif pgx_no_match:
            pgx_suffix = f"  💊 нет данных (в базе {pgx_no_match['total_annotations']})"
        else:
            pgx_suffix = ""

        if st == "matched":
            gt = r.get("matched_genotype", "")
            matches = r.get("matches", [])
            if len(matches) > 1:
                print(f"  {icon} {gene:14} → совпадений: {len(matches)}{pgx_suffix}")
                for m in matches:
                    row = m["full_row"]
                    risk = _pick_risk(row)
                    acmg = _strip_md(row.get("ACMG", ""))
                    print(f"        • {m['genotype']:20} | риск: {risk[:30]:30} | ACMG: {acmg}")
            else:
                row = r.get("full_row") or {}
                risk = _pick_risk(row)
                acmg = _strip_md(row.get("ACMG", ""))
                print(f"  {icon} {gene:14} → {gt:20} | "
                      f"риск: {risk[:30]:30} | ACMG: {acmg}{pgx_suffix}")
        elif st == "no_table_in_base":
            print(f"  {icon} {gene:14} → нет таблицы в базе{pgx_suffix}")
        elif st == "no_genotype_match":
            print(f"  {icon} {gene:14} → не сопоставлен{pgx_suffix}")
        else:
            print(f"  {icon} {gene:14} → нет в базе знаний{pgx_suffix}")

    print()


# ============================================================
#  Markdown
# ============================================================

def save_markdown(reports: list[dict], path: str):
    L = ["# Отчёт по генетическим анализам", ""]

    for rep in reports:
        s = rep["stats"]
        L.append(f"## {rep['file']}")
        L.append("")
        L.append(f"- Генов: **{rep['genes_total']}**")
        L.append(f"- ✅ Совпало: **{s['matched']}**")
        L.append(f"- 🟡 Нет таблицы в базе: **{s['no_table_in_base']}**")
        L.append(f"- ⚠️ Не найден генотип: **{s['no_genotype_match']}**")
        L.append(f"- ❌ Нет в базе: **{s['not_in_knowledge_base']}**")
        L.append("")

        L.append("| Ген | Результат | Совпавший генотип | Риск | ACMG | Статус |")
        L.append("|---|---|---|---|---|---|")
        for r in rep["results"]:
            gt = r.get("matched_genotype") or "—"
            row = r.get("full_row") or {}
            risk = _pick_risk(row) if row else "—"
            acmg = _strip_md(row.get("ACMG", "—")) if row else "—"
            L.append(f"| {r['gene']} | {r['patient_result'][:60]} | {gt} | "
                     f"{risk[:40]} | {acmg} | `{r['status']}` |")
        L.append("")

        matched = [r for r in rep["results"] if r["status"] == "matched"]
        if matched:
            L.append("### ✅ Совпавшие гены")
            L.append("")
            for r in matched:
                L.append(f"#### {r['gene']}")
                L.append("")
                L.append(f"**Результат пациента:** {r['patient_result']}  ")
                L.append(f"**Группа:** {r['group']}  ")
                L.append("")
                for m in r.get("matches", []):
                    L.append(f"**Вариант:** `{m.get('source_part','')}` → "
                             f"**генотип** `{m['genotype']}`")
                    L.append("")
                    for k, v in m["full_row"].items():
                        if v:
                            L.append(f"- **{k}:** {_strip_md(v)}")
                    L.append("")

                pgx = r.get("pgx_annotations", [])
                if pgx:
                    L.append("**💊 Фармакогенетика (только ваше):**")
                    L.append("")
                    L.append("| Совп. | Категория | Препарат | Ассоциация | P-value |")
                    L.append("|---|---|---|---|---|")
                    for a in pgx:
                        icon = "✅" if a.get("match_kind") == "exact" else "◐"
                        L.append(f"| {icon} | {a['phenotype']} | {a['drug']} | "
                                 f"{a['association'][:160]} | {a['pvalue']} |")
                    L.append("")

                no_match = r.get("pgx_no_match_info")
                if no_match:
                    pgt = ", ".join(no_match.get("patient_genotypes", [])) or "—"
                    bgt = ", ".join(no_match.get("genotypes_in_base", [])[:15])
                    L.append(f"**💊 Фармакогенетика:** нет данных для генотипа `{pgt}`. "
                             f"В базе {no_match['total_annotations']} ассоциаций для "
                             f"генотипов: {bgt}.")
                    L.append("")

                if r["recommendations"]:
                    L.append("**Рекомендации из базы:**")
                    L.append("")
                    for rec in r["recommendations"]:
                        L.append(f"- {rec}")
                L.append("")

    Path(path).write_text("\n".join(L), encoding="utf-8")


# ============================================================
#  main
# ============================================================

def main():
    print("Загрузка базы знаний…")
    base = load_base(BASE_PATH)
    gene_index = build_gene_index(base)
    print(f"  Генов в базе: {len(gene_index)}\n")

    samples = []
    for name in sorted(os.listdir(SAMPLES_DIR)):
        if not name.lower().endswith(('.txt', '.docx')):
            continue
        path = os.path.join(SAMPLES_DIR, name)
        print(f"Обработка: {name}")
        rep = process_sample(path, gene_index)
        samples.append(rep)
        print_sample_report(rep)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    save_markdown(samples, OUT_MD)

    print(f"💾 JSON: {OUT_JSON}")
    print(f"💾 Markdown: {OUT_MD}")


if __name__ == "__main__":
    main()