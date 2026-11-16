"""
Интерпретатор генетических анализов (v14).
Ключевое отличие от v13:
- Если у гена нет таблицы генотипов, но есть рекомендации или фармакогенетика,
  он получает статус "matched_annotation_only" (условно зеленый).
- Добавлены варианты в KNOWN_VARIANTS для улучшения матчинга.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional


BASE_PATH = "data/parsed_knowledge_base_clean.json"
SAMPLES_DIR = "samples"
OUT_JSON = "reports/patient_report.json"
OUT_MD = "reports/patient_report.md"


NORMAL_PHRASES = [
    'не обнаружено', 'не выявлено', 'норма', 'нормально',
    'дикий тип', 'wild type', 'без мутаций', 'не носитель',
]

NON_GENOTYPE_COLUMNS = {
    'вариант', 'лекарство', 'эффект', 'уровень',
    'препарат', 'guidance', 'источник', 'домен',
    'rsid', 'изоформа',
}

# Расширенный словарь для правильного извлечения генотипов из названий вариантов
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
    # Новые добавленные варианты
    'r653q': ('C', 'T'),
    'rs1801133': ('C', 'T'),
    'rs1805087': ('A', 'G'),
    'rs1801394': ('A', 'G'),
    'p187s': ('C', 'T'),  # NQO1
    'mthfd1_r653q': ('G', 'A'),  # MTHFD1 (rs2236225)
    # DPYD star allele → HGVS (not a ref/alt nucleotide pair).
    '*2a': 'c.1905+1G>A',
    '*13': 'c.1679T>G',
    '*9a': 'c.85T>C',
}

# ============================================================
#  Загрузка базы знаний
# ============================================================

def load_base(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def extract_gene_name(header: str) -> str:
    try:
        from genedb.catalog import extract_gene_symbols
        symbols = extract_gene_symbols(header)
        if symbols:
            return symbols[0]
    except ImportError:
        pass
    m = re.match(r'^([A-Z0-9/* \-]+)\s+[—–]', header.strip())
    if m:
        return m.group(1).strip().split("/")[0].strip()
    return header.split()[0] if header.split() else header

def build_gene_index(base: list[dict]) -> dict:
    try:
        from genedb.catalog import extract_gene_symbols as _symbols
    except ImportError:
        def _symbols(header: str) -> list[str]:
            return [extract_gene_name(header).upper()]

    index: dict[str, tuple] = {}
    for group in base:
        for gene in group["genes"]:
            entry = (group["group"], gene)
            for sym in _symbols(gene["header"]):
                key = sym.upper().replace(" ", "")
                index[key] = entry
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
        # Stop a field at blank lines and at separator lines (=..., ---...).
        if not line or line.startswith("=") or line.startswith("-"):
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
            # Result is the rest of this line only — do not glue following rows.
            current["result"] = m.group(1).strip()
            last_field = None
            continue

        m = RE_COMMENT.match(line)
        if m:
            current["comment"] = m.group(1).strip()
            last_field = "comment"
            continue

        if last_field == "comment":
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

def read_pdf(path: str) -> str:
    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError("Для PDF нужен pdfplumber. Установите: pip install pdfplumber") from e
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_patient_input(text: str, path: Optional[str] = None) -> list[dict]:
    """Dispatch: HL7 v2 vs mixed VCF/lab dump vs classic Ген/Результат text."""
    from hl7_parser import looks_like_hl7, parse_hl7_report
    from raw_parser import looks_like_raw_lab, parse_raw_lab_report

    if looks_like_hl7(text, path):
        return parse_hl7_report(text)
    if looks_like_raw_lab(text, path):
        return parse_raw_lab_report(text)
    return parse_patient_report(text)


def read_any(path: str) -> str:
    low = path.lower()
    if low.endswith(".docx"):
        return read_docx(path)
    if low.endswith(".pdf"):
        return read_pdf(path)
    return read_txt(path)

# ============================================================
#  Извлечение генотипов пациента
# ============================================================

_POLARITY_RE = re.compile(
    r"(?i)\b(?:positive|negative|позитивн\w*|негативн\w*)\b|\(\+\)|\(-\)"
)
# HLA alleles use colon fields (*07:01). Do not match CYP diplotype parts (*1/*2).
RE_HLA_ALLELE = re.compile(r"(\*\d+(?::\d+){1,3})")
RE_SIMPLE_LETTER_PAIR = re.compile(r"(?<![A-Za-z])([A-Za-z]{2})(?![A-Za-z])")


def _strip_polarity(gt: str) -> str:
    """Remove Positive/Negative/(+)/(-) markers from genotype strings.

    HLA results such as '*15:02 Positive' become '*15:02'.
    """
    if not gt:
        return ""
    return _POLARITY_RE.sub(" ", gt).strip()


def _polarity(gt: str) -> str:
    low = (gt or "").lower()
    if "positive" in low or "(+)" in low or "позитив" in low:
        return "pos"
    if "negative" in low or "(-)" in low or "негатив" in low:
        return "neg"
    return ""


def _is_simple_letter_pair(gt: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]{2}", (gt or "").strip()))


def _normalize(gt: str) -> str:
    if not gt:
        return ""
    s = gt.strip()
    s = re.sub(r"\s*\(.*?\)", "", s)
    s = _strip_polarity(s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""
    # HLA / star alleles: keep '*' and digits/colons, drop spaces.
    if "*" in s:
        return s.replace(" ", "").lower()
    # Sports / protein genotypes (RR, RX, XX, etc.): keep letter order.
    if _is_simple_letter_pair(s) and not all(c in "ACGTacgt" for c in s):
        return s.upper()
    s = s.replace("/", "").replace(" ", "").replace("|", "").lower()
    if len(s) == 2 and all(c in "acgt" for c in s):
        return "".join(sorted(s))
    return s

def _is_normal(result: str) -> bool:
    low = result.lower()
    if re.search(r"\bне\s+норм", low):
        return False
    for phrase in NORMAL_PHRASES:
        if phrase == "норма":
            if re.search(r"(?<!\w)норма(?!\w)", low):
                return True
        elif phrase in low:
            return True
    return False

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
# RE_HLA_ALLELE / RE_SIMPLE_LETTER_PAIR defined near _normalize.

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

def _star_hgvs_diplotype(text: str) -> str:
    """'*2A/*2A' → 'c.[1905+1G>A];[1905+1G>A]' when both alleles are mapped."""
    alleles = re.findall(r"\*(\d+[A-Za-z]?)", text or "")
    if len(alleles) < 2:
        return ""
    bodies: list[str] = []
    for allele in alleles[:2]:
        spec = KNOWN_VARIANTS.get(f"*{allele}".lower())
        if not isinstance(spec, str):
            return ""
        body = spec[2:] if spec.lower().startswith("c.") else spec
        if not body:
            return ""
        bodies.append(body)
    return f"c.[{bodies[0]}];[{bodies[1]}]"


def _hgvs_diplotype_in_row(candidate_norm: str, row_norm: str) -> bool:
    """True when a phased HGVS diplotype sits inside a longer genotype cell."""
    if "c.[" not in candidate_norm or "];[" not in candidate_norm:
        return False
    return candidate_norm in row_norm


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

    # Keep original + polarity-stripped forms (HLA: "*15:02 Positive" → "*15:02").
    add(r)
    stripped = _strip_polarity(r)
    stripped = re.sub(r"\s*\(.*?\)", "", stripped).strip()
    if stripped and stripped != r:
        add(stripped)
    hgvs = _star_hgvs_diplotype(stripped or r)
    if hgvs:
        add(hgvs)

    # Whole-result sports / letter-pair genotypes: RR, RX, XX, etc.
    if _is_simple_letter_pair(r):
        add(r.upper())
        add(r)

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

    # HLA alleles with fields: *07:01, *15:01 (not CYP *1/*2 parts).
    for m in RE_HLA_ALLELE.finditer(r):
        add(m.group(1))

    # Whole-result single star allele only (e.g. "*2"), not parts of "*1/*2".
    if re.fullmatch(r"\*\d+", stripped.replace(" ", "")):
        add(stripped.replace(" ", ""))

    for m in re.finditer(r'([A-Za-zА-Яа-я0-9*]+(?:/[A-Za-zА-Яа-я0-9*]+)+)', r):
        val = m.group(1)
        if len(val) <= 12:
            add(val)

    r_low = r.lower()
    for name, spec in KNOWN_VARIANTS.items():
        if not isinstance(spec, tuple):
            continue
        ref, mut = spec
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

    if not candidates or len(candidates) <= 2:
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

    # Letter pairs for sports genes (RR/RX/XX) — always, not only het/hom wording.
    for m in RE_SIMPLE_LETTER_PAIR.finditer(r):
        pair = m.group(1)
        if pair.upper() == pair or not all(c in "ACGTacgt" for c in pair):
            add(pair.upper())
            add(pair)

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

def _star_haplotype_parts(value: str) -> list[str]:
    return [p for p in value.replace(" ", "").split("/") if p.startswith("*")]


def _is_star_overlap(cn: str, row_norm: str) -> bool:
    if "*" not in cn and "*" not in row_norm:
        return False
    c_parts = _star_haplotype_parts(cn)
    if not c_parts:
        return cn == row_norm
    c_set = set(c_parts)
    # PGx tables often list several diplotypes in one cell: "*1/*2, *1/*3, *2/*17".
    for chunk in re.split(r"[,;]", row_norm.replace(" ", "")):
        r_chunk = _star_haplotype_parts(chunk)
        if r_chunk and set(r_chunk) == c_set:
            return True
    r_parts = _star_haplotype_parts(row_norm)
    if not r_parts:
        return cn == row_norm
    if len(c_parts) == 1 and "/" not in cn.replace(" ", ""):
        return c_parts[0] in r_parts
    return c_set == set(r_parts)


def _canonical_star_diplotype(candidate: str) -> str:
    """'*1/*2' from a patient candidate; empty if it is not a star genotype."""
    parts = _star_haplotype_parts(_normalize(candidate))
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    if len(parts) == 1:
        return parts[0]
    return ""


def _specific_matched_genotype(row_gt: str, candidate: str) -> str:
    """Display the patient's star diplotype, not the whole comma-separated KB cell."""
    star = _canonical_star_diplotype(candidate)
    if star and _is_star_overlap(_normalize(candidate), _normalize(row_gt)):
        return star
    return row_gt


def _row_with_specific_genotype(row: dict, display_gt: str, matched_column: Optional[str]) -> dict:
    """Copy a KB row and replace the genotype cell with the patient's match."""
    out = dict(row)
    if matched_column and matched_column in out:
        out[matched_column] = display_gt
        return out
    for k in out:
        hl = k.strip().lower()
        if hl in {"генотип", "genotype"} or hl.startswith("генотип"):
            out[k] = display_gt
            break
    return out

def find_genotype_rows_for_candidates(gene: dict, candidates: list[str]) -> list[dict]:
    if not candidates:
        return []
    cand_norm = [
        (c, _normalize(c), _polarity(c))
        for c in candidates
        if _normalize(c)
    ]
    if not cand_norm:
        return []
    # If the patient result includes Positive/Negative, only accept rows
    # with the same polarity (avoid "*07:01" matching both).
    patient_pols = {p for _, _, p in cand_norm if p}

    GT_COLUMNS = {'генотип', 'аллели', 'alleles', 'genotype'}

    def is_gt_col(h: str) -> bool:
        hl = h.strip().lower()
        return hl in GT_COLUMNS or hl.startswith('генотип') or hl.startswith('аллели')

    matches = []
    seen_rows = set()
    seen_genotypes = set()

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
                # Prefer polarity-aligned / direct letter-pair hits.
                best_match = None
                best_score = -1

                for gt_col in gt_cols:
                    row_gt = row.get(gt_col, "").strip()
                    if not row_gt:
                        continue
                    row_norm = _normalize(row_gt)
                    row_pol = _polarity(row_gt)
                    if patient_pols and row_pol and row_pol not in patient_pols:
                        continue
                    row_gt_u = row_gt.strip().upper()
                    for orig, cn, c_pol in cand_norm:
                        matched = False
                        score = 0
                        # Direct string match for sports letter pairs (RR/RX/XX).
                        if _is_simple_letter_pair(orig) and _is_simple_letter_pair(row_gt):
                            if orig.strip().upper() == row_gt_u:
                                matched = True
                                score = 3
                        if not matched and cn == row_norm:
                            matched = True
                            score = 2
                        elif not matched and cn.replace('/', '') == row_norm.replace('/', ''):
                            matched = True
                            score = 1
                        elif not matched and _is_star_overlap(cn, row_norm):
                            matched = True
                            score = 1
                        elif not matched and _hgvs_diplotype_in_row(cn, row_norm):
                            matched = True
                            score = 2
                        if not matched:
                            continue
                        # Reject HLA Positive vs Negative mismatches.
                        if c_pol and row_pol and c_pol != row_pol:
                            continue
                        if c_pol and row_pol and c_pol == row_pol:
                            score += 2
                        if score > best_score:
                            best_score = score
                            best_match = (row_gt, orig, gt_col)

                if not best_match:
                    continue
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)

                row_gt, orig, gt_col = best_match
                display_gt = _specific_matched_genotype(row_gt, orig)
                # Prefer patient letter-pair / HLA allele / phased HGVS display.
                if "c.[" in (orig or "") and "];[" in (orig or ""):
                    display_gt = orig.strip()
                elif _is_simple_letter_pair(orig):
                    display_gt = orig.strip().upper()
                elif _polarity(orig) or RE_HLA_ALLELE.search(orig or ""):
                    display_gt = _strip_polarity(orig) or display_gt
                gkey = _normalize(display_gt) or _normalize(row_gt)
                # Include polarity in dedupe key so Positive/Negative stay distinct
                # when both somehow match without patient polarity.
                gkey_full = f"{gkey}|{_polarity(row_gt)}"
                if gkey_full in seen_genotypes:
                    continue
                seen_genotypes.add(gkey_full)
                matches.append({
                    "section": sec, "table": tbl, "row": row,
                    "matched_field": display_gt, "matched_candidate": orig, "matched_column": gt_col,
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
                    return {"section": sec, "table": tbl, "row": row, "matched_field": _strip_md(row_gt), "matched_candidate": "норма"}
    return None

# ============================================================
#  Фармакогенетика
# ============================================================

def _extract_patient_alleles(result: str) -> set:
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
    if not assoc:
        return ""
    text = assoc
    cut_markers = ['More Details:', 'Note:', 'Alleles complemented', 'Please note', 'Alleles have been', 'Alleles given']
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

                assoc_genotypes = _extract_genotypes_from_association(assoc)
                patient_norm = {a.upper().replace('/', '') for a in patient_alleles}

                matched_genotypes = []
                match_kind = None
                is_matched = False

                for g in assoc_genotypes:
                    g_norm = g.upper().replace('/', '')
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
                    if len(g_norm) == 1:
                        for p in patient_norm:
                            if len(p) == 2 and p.count(g_norm) == 2:
                                is_matched = True
                                match_kind = match_kind or 'allele'
                                matched_genotypes.append(g)
                                break
                            if len(p) == 2 and p[0] != p[1] and g_norm in p:
                                is_matched = True
                                match_kind = match_kind or 'allele'
                                matched_genotypes.append(g)
                                break

                if not is_matched:
                    continue

                all_matches.append({
                    "variant": row.get("Variant", "").strip(),
                    "drug": row.get("Drug", "").strip() or "—",
                    "association": _clean_assoc(assoc),
                    "association_raw": assoc,
                    "pvalue": row.get("P-value", "").strip() or "—",
                    "pvalue_num": _parse_pvalue(row.get("P-value", "")),
                    "phenotype": row.get("Phenotype", "").strip() or "Other",
                    "assoc_genotypes": assoc_genotypes,
                    "matched_genotypes": matched_genotypes,
                    "match_kind": match_kind,
                    "section": sec.get("code", "") + " " + sec.get("title", ""),
                })

    seen = set()
    unique = []
    for m in all_matches:
        key = (m["drug"], m["association"][:100])
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)

    unique.sort(key=lambda x: (0 if x["match_kind"] == "exact" else 1, x["pvalue_num"]))
    matches = unique[:top_n]

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

    return {"matches": matches, "no_match_info": no_match_info}

# ============================================================
#  Интерпретация гена
# ============================================================

_SKIP_REC = re.compile(
    r"et al\.|jaiswal|мыши|мышь|in vitro|pmid|pmcid|omim \*|mouse|mice",
    re.IGNORECASE,
)
_ACTION_REC = re.compile(
    r"(рекомендуется|рекомендуются|снизить|снижение|контроль|избегать|замена|"
    r"мониторинг|противопоказан|не рекоменду|требуется|не назначать|начальная\s+доза)",
    re.IGNORECASE,
)


def _is_actionable_recommendation(text: str) -> bool:
    t = _strip_md(text or "").strip()
    if not t or len(t) > 250:
        return False
    if _SKIP_REC.search(t):
        return False
    return bool(_ACTION_REC.search(t))


def _collect_recommendations(gene: dict) -> list[str]:
    recs = []
    seen = set()
    for sec in gene["sections"]:
        for raw in sec.get("bullets", []):
            t = _strip_md(str(raw)).strip()
            if not _is_actionable_recommendation(t):
                continue
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            recs.append(t)
    return recs if recs else ["Специфических рекомендаций нет"]


# Variant evidence used when the lab comment does not already name an rsID.
_STAR_EVIDENCE = {
    "CYP2C19": {"*2": "rs4244285 G>A", "*3": "rs4986893 G>A", "*17": "rs12248560 C>T"},
    "CYP2C9": {"*2": "rs1799853 C>T", "*3": "rs1057910 A>C"},
}
_GENE_RSID_EVIDENCE = {
    "MTHFR": "rs1801133 C>T",
    "F5": "rs6025 C>T",
    "F2": "rs1799963 G>A",
    "NQO1": "rs1800566 C>T",
    "SLCO1B1": "rs4149056 T>C",
    "APOE": "rs429358 T>C / rs7412 C>T",
    "VKORC1": "rs9923231 C>T",
}
_CPIC_BY_DRUG = {
    "клопидогрел": "CPIC Guideline for Clopidogrel (2022)",
    "clopidogrel": "CPIC Guideline for Clopidogrel (2022)",
    "варфарин": "CPIC Guideline for Warfarin (2017)",
    "warfarin": "CPIC Guideline for Warfarin (2017)",
    "фенитоин": "CPIC Guideline for Phenytoin (2020)",
    "phenytoin": "CPIC Guideline for Phenytoin (2020)",
    "симвастатин": "CPIC Guideline for Statins (2022)",
    "statin": "CPIC Guideline for Statins (2022)",
    "омепразол": "CPIC Guideline for Proton Pump Inhibitors (2020)",
    "лансопразол": "CPIC Guideline for Proton Pump Inhibitors (2020)",
}
_CPIC_BY_GENE = {
    "CYP2C19": "CPIC Guideline for Clopidogrel (2022)",
    "CYP2C9": "CPIC Guideline for Warfarin (2017)",
    "SLCO1B1": "CPIC Guideline for Statins (2022)",
    "CYP2D6": "CPIC Guideline for CYP2D6 substrates",
    "VKORC1": "CPIC Guideline for Warfarin (2017)",
}


def _phenotype_codes(pheno: str) -> set[str]:
    codes: set[str] = set()
    if not pheno:
        return codes
    for m in re.finditer(r"\b(IM|PM|NM|UM|RM|EM)\b", pheno, re.I):
        codes.add(m.group(1).upper())
    low = pheno.lower()
    if "intermediate" in low or "промежуточ" in low:
        codes.add("IM")
    if "poor metabol" in low or "медленн" in low:
        codes.add("PM")
    if "normal metabol" in low or "extensive" in low:
        codes.add("NM")
    return codes


def _evidence_from_text(blob: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"(rs\d+)(?:\s+([ACGT])\s*[/>]\s*([ACGT]))?", blob or "", re.I):
        rsid = m.group(1).lower()
        if rsid in seen:
            continue
        seen.add(rsid)
        if m.group(2) and m.group(3):
            ref, alt = m.group(2).upper(), m.group(3).upper()
            if ref == alt:
                continue
            found.append(f"{rsid} {ref}>{alt}")
        else:
            found.append(rsid)
    return found


def _evidence_from_stars(gene_name: str, result: str) -> list[str]:
    mapping = _STAR_EVIDENCE.get(gene_name.upper(), {})
    out: list[str] = []
    for star in re.findall(r"\*\d+", result or ""):
        item = mapping.get(star)
        if item and item not in out:
            out.append(item)
    return out


def _pick_guideline(gene_name: str, drug: str, kb_source: str) -> str:
    drug_l = (drug or "").lower()
    src_u = (kb_source or "").upper()
    for key, title in _CPIC_BY_DRUG.items():
        if key in drug_l and (not kb_source or "CPIC" in src_u):
            return title
    if kb_source:
        extra = f" ({drug})" if drug else ""
        return f"{kb_source}{extra}"
    return _CPIC_BY_GENE.get(gene_name.upper(), "GenomIQ knowledge base")


def _source_from_gene_tables(gene: Optional[dict], gene_name: str, pheno: str) -> str:
    if not gene:
        return _CPIC_BY_GENE.get(gene_name.upper(), "GenomIQ knowledge base")
    codes = _phenotype_codes(pheno)
    ranked: list[str] = []
    for sec in gene.get("sections", []):
        for tbl in sec.get("tables", []):
            headers = tbl.get("headers") or []
            src_col = next((h for h in headers if "источник" in h.lower() or "source" in h.lower()), None)
            if not src_col:
                continue
            gt_col = next((h for h in headers if "генотип" in h.lower() or "фенотип" in h.lower()), None)
            drug_col = next((h for h in headers if "препарат" in h.lower() or "drug" in h.lower()), None)
            for row in tbl.get("rows") or []:
                src = _strip_md(str(row.get(src_col, "") or "")).strip()
                if not src:
                    continue
                gt = str(row.get(gt_col, "") or "") if gt_col else ""
                drug = _strip_md(str(row.get(drug_col, "") or "")).strip() if drug_col else ""
                if codes and gt and not any(c in gt.upper() for c in codes):
                    continue
                ranked.append(_pick_guideline(gene_name, drug, src))
        blob = " ".join(sec.get("bullets") or []) + " " + (sec.get("text") or "")
        m = re.search(r"CPIC[^\n.*]{0,60}", blob, re.I)
        if m and "отсутств" not in m.group(0).lower():
            ranked.append(m.group(0).strip().rstrip(" ,;"))
    if ranked:
        return ranked[0]
    return _CPIC_BY_GENE.get(gene_name.upper(), "GenomIQ knowledge base")


def build_why_evidence(patient_gene: dict, gene: Optional[dict], info: dict) -> dict:
    """Exact evidence for the HTML Why? block: source, variant, annotation."""
    name = info.get("gene") or patient_gene.get("gene", "")
    gt = info.get("matched_genotype") or patient_gene.get("result", "") or "—"
    row = info.get("full_row") or {}
    pheno = _strip_md(str(row.get("Фенотип") or row.get("Phenotype") or "")).strip()
    annotation = _strip_md(
        str(row.get("Клинический риск") or row.get("Clinical risk") or "")
    ).strip()
    if not annotation:
        recs = info.get("recommendations") or []
        annotation = recs[0] if recs else ""

    comment = patient_gene.get("comment") or info.get("patient_comment") or ""
    evidence_bits = _evidence_from_text(f"{patient_gene.get('result', '')} {comment}")
    if not evidence_bits:
        evidence_bits = _evidence_from_stars(name, patient_gene.get("result") or gt)
    if not evidence_bits:
        fallback = _GENE_RSID_EVIDENCE.get(name.upper())
        if fallback:
            evidence_bits = [fallback]
    evidence = "; ".join(evidence_bits)

    source = _source_from_gene_tables(gene, name, pheno)
    parts = [f"{name} {gt}".strip()]
    if pheno:
        parts[0] = f"{name} {gt} → {pheno}"
    sentence = parts[0] + "."
    if source:
        sentence += f" Source: {source}."
    if evidence:
        sentence += f" Evidence: {evidence}."
    return {
        "sentence": sentence,
        "source": source,
        "evidence": evidence,
        "phenotype": pheno,
        "annotation": annotation,
    }


def _with_why(info: dict, patient_gene: dict, gene: Optional[dict] = None) -> dict:
    info["why"] = build_why_evidence(patient_gene, gene, info)
    row = info.get("full_row") or {}
    info["clinical_risk"] = _strip_md(
        str(row.get("Клинический риск") or row.get("Clinical risk") or "")
    ).strip()
    return info


def _result_gt_blob(r: dict) -> str:
    parts = [r.get("patient_result") or "", r.get("matched_genotype") or ""]
    for m in r.get("matches") or []:
        parts.append(m.get("genotype") or "")
    return " ".join(parts)


def _nuc_pair(blob: str) -> str:
    s = re.sub(r"\([^)]*\)", "", blob or "")
    s = s.replace("/", "").replace("|", "").replace(" ", "")
    m = re.search(r"[ACGTacgt]{2}", s)
    if not m:
        return ""
    pair = m.group(0).upper()
    return "".join(sorted(pair)) if pair[0] != pair[1] else pair


def _star_pair(blob: str) -> str:
    m = re.search(r"(\*\d+)\s*/\s*(\*\d+)", blob or "")
    if not m:
        return ""
    a, b = m.group(1), m.group(2)
    ordered = sorted([a, b], key=lambda x: int(x[1:] or 0))
    return f"{ordered[0]}/{ordered[1]}"


def collect_critical_alerts(results: list) -> list[dict]:
    """High-risk combinations for the HTML critical-alert banner."""
    alerts = []
    seen = set()
    for r in results or []:
        gene = (r.get("gene") or "").upper()
        blob = _result_gt_blob(r)
        nuc = _nuc_pair(blob)
        star = _star_pair(blob)
        text = None
        key = None
        if gene == "F5" and nuc in {"CT", "TT"}:
            key, text = "F5", (
                "Гормональные контрацептивы не рекомендуются (требуется индивидуальная оценка; "
                "риск тромбоза, RR=34.7). Решение о применении должно приниматься врачом "
                "с учетом семейного тромботического анамнеза."
            )
        elif gene == "F2" and nuc in {"AG", "AA"}:
            key, text = "F2", (
                "Гормональные контрацептивы не рекомендуются (требуется индивидуальная оценка). "
                "Решение о применении должно приниматься врачом с учетом семейного "
                "тромботического анамнеза."
            )
        elif gene == "CYP2C19" and star in {"*1/*2", "*2/*2", "*2/*3", "*3/*3"}:
            key, text = "CYP2C19", (
                "Снижение эффективности клопидогреля. Рекомендуется замена на тикагрелор или прасугрел."
            )
        elif gene == "MTHFR" and nuc == "TT":
            key, text = "MTHFR", (
                "Ассоциация с повышением гомоцистеина; контроль уровня гомоцистеина. "
                "Клиническая значимость для тромбоза/невынашивания обсуждается "
                "(ACMG не рекомендует рутинное тестирование)."
            )
        elif gene == "SLCO1B1" and nuc in {"CT", "CC"}:
            key, text = "SLCO1B1", (
                "Повышенный риск миопатии на симвастатине. Снизить дозу или заменить на розувастатин/правастатин."
            )
        if key and key not in seen:
            seen.add(key)
            alerts.append({"gene": key, "genotype": r.get("patient_result") or "", "text": text})
    return alerts


def build_doctors_note(results: list) -> str:
    """Selectable clinical summary for the referring physician."""
    sentences = []
    for r in results or []:
        if r.get("status") not in {"matched", "matched_annotation_only"}:
            continue
        gene = (r.get("gene") or "").upper()
        blob = _result_gt_blob(r)
        nuc = _nuc_pair(blob)
        star = _star_pair(blob)
        gt = (r.get("patient_result") or r.get("matched_genotype") or "").strip()
        risk = (r.get("clinical_risk") or "").strip()
        if gene == "F5" and nuc in {"CT", "TT"}:
            zyg = "гомозиготная" if nuc == "TT" else "гетерозиготная"
            sentences.append(
                f"У пациента выявлена {zyg} мутация F5 (Лейден). "
                "Гормональные контрацептивы не рекомендуются (требуется индивидуальная оценка); "
                "решение о применении должно приниматься врачом с учетом семейного "
                "тромботического анамнеза; контроль гематолога."
            )
        elif gene == "F2" and nuc in {"AG", "AA"}:
            sentences.append(
                "Выявлен вариант F2 G20210A — гормональные контрацептивы не рекомендуются "
                "(требуется индивидуальная оценка); решение о применении должно приниматься "
                "врачом с учетом семейного тромботического анамнеза."
            )
        elif gene == "CYP2C19" and star in {"*1/*2", "*2/*2", "*2/*3", "*3/*3"}:
            sentences.append(
                f"Выявлена мутация CYP2C19 {star} — снижение эффективности клопидогреля, "
                "рекомендована замена на тикагрелор."
            )
        elif gene == "MTHFR" and nuc == "TT":
            sentences.append(
                "Выявлена гомозиготная мутация MTHFR C677T (TT) — ассоциация с повышением "
                "гомоцистеина; контроль гомоцистеина. Клиническая значимость для "
                "тромбоза/невынашивания обсуждается (ACMG не рекомендует рутинное тестирование)."
            )
        elif gene == "SLCO1B1" and nuc in {"CT", "CC"}:
            sentences.append(
                "Выявлен вариант SLCO1B1 — повышенный риск миопатии на симвастатине; "
                "снизить дозу или заменить на розувастатин/правастатин."
            )
        elif risk and "специфических рекомендаций нет" not in risk.lower():
            sentences.append(f"{gene} ({gt}): {risk.rstrip('.')}." )
    return " ".join(sentences)

def split_result_into_parts(result: str) -> list[str]:
    parts = re.split(r',\s*(?=(?:[A-Za-z]{1,3}[\d\.]*[A-Za-z]|rs\d|\*))', result)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if len(parts) > 1 else [result.strip()]

def _try_deletion_genes(raw_name, patient_gene, gene, group_name, pgx_result):
    if raw_name.upper() not in ('GSTM1', 'GSTT1'):
        return None
    res_low = patient_gene["result"].lower()
    if not ('норма' in res_low or 'non-null' in res_low or 'null' in res_low):
        return None
    recommendations = _collect_recommendations(gene)

    target_gt = 'non-null' if ('норма' in res_low or 'non-null' in res_low) else 'null'

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
                if target_gt in row_gt.lower():
                    return {
                        "gene": raw_name, "group": group_name,
                        "patient_result": patient_gene["result"],
                        "patient_comment": patient_gene.get("comment", ""),
                        "parts": [patient_gene["result"]],
                        "extracted_candidates": [row_gt],
                        "has_genotype_table": True,
                        "recommendations": recommendations,
                        "status": "matched",
                        "matches": [{"genotype": _strip_md(row_gt), "full_row": row, "source_part": patient_gene["result"]}],
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
                    if not cell_val: continue
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
                            "matches": [{"genotype": clean_isoform, "full_row": row, "source_part": patient_gene["result"]}],
                            "matched_genotype": clean_isoform,
                            "full_row": row,
                            "pgx_annotations": pgx_result["matches"],
                            "pgx_no_match_info": pgx_result["no_match_info"],
                        }
    return None

def interpret_gene(patient_gene: dict, gene_index: dict) -> dict:
    raw_name = patient_gene["gene"].strip()
    name_upper = raw_name.upper()

    compact = re.sub(r"\s+", "", name_upper)
    base_entry = gene_index.get(compact) or gene_index.get(name_upper)
    if base_entry is None:
        for key, entry in gene_index.items():
            if re.sub(r"\s+", "", key) == compact:
                base_entry = entry
                break

    if base_entry is None:
        return _with_why({
            "gene": raw_name, "patient_result": patient_gene["result"],
            "patient_comment": patient_gene.get("comment", ""),
            "status": "not_in_knowledge_base", "matches": [],
            "pgx_annotations": [], "pgx_no_match_info": None,
        }, patient_gene, None)

    group_name, gene = base_entry

    patient_alleles = _extract_patient_alleles(patient_gene.get("result", ""))
    patient_alleles |= _extract_patient_alleles(patient_gene.get("comment", ""))
    pgx_result = find_pgx_annotations(gene, patient_alleles)

    special = _try_deletion_genes(raw_name, patient_gene, gene, group_name, pgx_result)
    if special is not None:
        return _with_why(special, patient_gene, gene)

    apoe_special = _try_apoe_isoform(raw_name, patient_gene, gene, group_name, pgx_result)
    if apoe_special is not None:
        return _with_why(apoe_special, patient_gene, gene)

    recommendations = _collect_recommendations(gene)
    has_table = has_real_genotype_table(gene)

    if _is_normal(patient_gene["result"]) and has_table:
        wild_row = _find_wild_type_row(gene)
        if wild_row:
            return _with_why({
                "gene": raw_name, "group": group_name,
                "patient_result": patient_gene["result"],
                "patient_comment": patient_gene.get("comment", ""),
                "parts": [patient_gene["result"]],
                "extracted_candidates": ["норма (дикий тип)"],
                "has_genotype_table": True,
                "recommendations": recommendations,
                "status": "matched",
                "matches": [{"genotype": wild_row["matched_field"], "full_row": wild_row["row"], "source_part": patient_gene["result"]}],
                "matched_genotype": wild_row["matched_field"],
                "full_row": wild_row["row"],
                "pgx_annotations": pgx_result["matches"],
                "pgx_no_match_info": pgx_result["no_match_info"],
            }, patient_gene, gene)

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
    seen_genotypes = set()
    for m in all_matches:
        row_key = tuple(sorted((k, str(v)) for k, v in m["row"].items() if v))
        gkey = _normalize(_strip_md(m.get("matched_field") or ""))
        if row_key in seen_rows or (gkey and gkey in seen_genotypes):
            continue
        seen_rows.add(row_key)
        if gkey:
            seen_genotypes.add(gkey)
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

    # === НОВАЯ ЛОГИКА ЗЕЛЁНОГО СТАТУСА ===
    has_any_data = bool(recommendations) or bool(pgx_result.get("matches"))

    if unique_matches:
        base_info["status"] = "matched"
        display_matches = []
        for m in unique_matches:
            display_gt = _strip_md(m["matched_field"])
            display_matches.append({
                "genotype": display_gt,
                "full_row": _row_with_specific_genotype(
                    m["row"], display_gt, m.get("matched_column")
                ),
                "source_part": m.get("source_part", ""),
            })
        base_info["matches"] = display_matches
        base_info["matched_genotype"] = ", ".join(m["genotype"] for m in display_matches)
        base_info["full_row"] = display_matches[0]["full_row"]
    elif not has_table and has_any_data:
        # Ген без таблицы генотипов, но с ассоциациями/рекомендациями — УСЛОВНО ЗЕЛЁНЫЙ
        base_info["status"] = "matched_annotation_only"
        base_info["matches"] = []
        base_info["matched_genotype"] = "Ассоциативный анализ"
        base_info["full_row"] = None
        base_info["note"] = "Для этого гена нет таблицы генотипов, но доступны клинические ассоциации или рекомендации."
    elif not has_table:
        base_info["status"] = "no_table_in_base"
        base_info["matches"] = []
        base_info["matched_genotype"] = None
        base_info["full_row"] = None
        base_info["note"] = "В базе знаний нет данных для этого гена."
    else:
        base_info["status"] = "no_genotype_match"
        base_info["matches"] = []
        base_info["matched_genotype"] = None
        base_info["full_row"] = None
        base_info["note"] = "Генотип не удалось сопоставить с таблицей базы. Проверьте вручную."

    return _with_why(base_info, patient_gene, gene)

# ============================================================
#  Обработка файла
# ============================================================

def save_markdown(reports: list[dict], path: str) -> None:
    """Краткий Markdown-отчёт для выгрузки из UI/CLI."""
    lines: list[str] = []
    for rep in reports:
        lines.append(f"# Отчёт: {rep.get('file', '')}\n")
        stats = rep.get("stats", {})
        lines.append(
            f"Генов: {rep.get('genes_total', 0)} | "
            f"matched: {stats.get('matched', 0)} | "
            f"annotation_only: {stats.get('matched_annotation_only', 0)} | "
            f"no_match: {stats.get('no_genotype_match', 0)} | "
            f"no_table: {stats.get('no_table_in_base', 0)} | "
            f"not_in_base: {stats.get('not_in_knowledge_base', 0)}\n"
        )
        for r in rep.get("results", []):
            lines.append(f"## {r.get('gene', '')} — {r.get('status', '')}")
            lines.append(f"Результат: {r.get('patient_result', '')}")
            if r.get("matched_genotype"):
                lines.append(f"Сопоставление: {r.get('matched_genotype')}")
            if r.get("note"):
                lines.append(f"Примечание: {r.get('note')}")
            lines.append("")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def process_sample(path: str, gene_index: dict) -> dict:
    text = read_any(path)
    patients = parse_patient_report(text)
    results = [interpret_gene(p, gene_index) for p in patients]

    stats = {
        "matched": sum(1 for r in results if r["status"] == "matched"),
        "matched_annotation_only": sum(1 for r in results if r["status"] == "matched_annotation_only"),
        "no_genotype_match": sum(1 for r in results if r["status"] == "no_genotype_match"),
        "no_table_in_base": sum(1 for r in results if r["status"] == "no_table_in_base"),
        "not_in_knowledge_base": sum(1 for r in results if r["status"] == "not_in_knowledge_base"),
    }

    return {"file": os.path.basename(path), "genes_total": len(results), "stats": stats, "results": results}

def main():
    print("Загрузка базы знаний…")
    base = load_base(BASE_PATH)
    gene_index = build_gene_index(base)
    print(f"  Генов в базе: {len(gene_index)}\n")

    samples = []
    for name in sorted(os.listdir(SAMPLES_DIR)):
        if not name.lower().endswith(('.txt', '.docx')): continue
        path = os.path.join(SAMPLES_DIR, name)
        print(f"Обработка: {name}")
        rep = process_sample(path, gene_index)
        samples.append(rep)
        # Упрощенный вывод для консоли
        print(f"  Генов: {rep['genes_total']} | ✅ {rep['stats']['matched'] + rep['stats']['matched_annotation_only']} | ⚠️ {rep['stats']['no_genotype_match']}")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    # save_markdown оставлен в v13, если он нужен, добавьте его обратно
    print(f"💾 JSON: {OUT_JSON}")

if __name__ == "__main__":
    main()