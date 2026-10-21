"""
md_parser.py — парсер Markdown-подобных .txt файлов с генами (v2).

Что нового:
- Распознаёт фармакогенетические таблицы (ClinPGx / PharmGKB):
    | Drug | Association | Sig | P-value | Phenotype |
  и складывает их в section["pharmacogenomics"].
- Обычные таблицы генотипов (| Генотип | Аллели | ... |) идут в section["tables"].
- Списки и текст — как раньше.
"""

import os
import re
import json
from typing import List, Dict, Any, Optional


# ---------- Регулярки ----------

RE_GROUP_TITLE = re.compile(r'^#\s+(.+)$')
RE_GENE_HEADER = re.compile(r'^##\s+ГЕН\s+(\d+):\s*(.+?)\s*$', re.IGNORECASE)
RE_SECTION = re.compile(r'^###\s+(\d+\.\d+)\s+(.+?)\s*$')
RE_INTRO = re.compile(r'^##\s+(Введение.+?)\s*$', re.IGNORECASE)
RE_INTERACTION = re.compile(r'^##\s+(Взаимодействия.+?)\s*$', re.IGNORECASE)
RE_TABLE_ROW = re.compile(r'^\|(.+)\|\s*$')
RE_LIST_ITEM = re.compile(r'^(\s*)-\s+(.+)$')


# Признаки фармакогенетической таблицы (по заголовкам колонок)
PGX_HEADER_HINTS = {
    'drug', 'drugs',
    'association',
    'sig', 'significance',
    'p-value', 'pvalue',
    'phenotype', 'phenotype categories',
    'literature', 'pmid', 'pmcid',
    '# of cases', '# of controls',
    'biogeographical groups',
    'more details',
}

# Признаки обычной таблицы генотипов
GENOTYPE_HEADER_HINTS = {
    'генотип', 'genotype',
    'аллели', 'alleles',
    'функциональный эффект',
    'клинический риск',
    'acmg',
    'частота', 'frequency',
    'фенотип', 'phenotype',
    'спортивный профиль',
}


# ---------- Парсинг таблиц ----------

def _parse_table_cells(line: str) -> List[str]:
    m = RE_TABLE_ROW.match(line.strip())
    if not m:
        return []
    inner = m.group(1)
    return [c.strip() for c in inner.split('|')]


def _classify_table(headers: List[str]) -> str:
    """
    Возвращает 'genotype' | 'pgx' | 'other' по набору заголовков.
    """
    h_low = {h.strip().lower() for h in headers}

    # Если есть drug + association / p-value / phenotype — это фармакогенетика
    pgx_score = sum(1 for h in h_low if any(hint in h for hint in PGX_HEADER_HINTS))
    gt_score = sum(1 for h in h_low if h in GENOTYPE_HEADER_HINTS)

    # Приоритет у фармакогенетики, если есть 'drug' или 'association'
    if 'drug' in h_low or 'drugs' in h_low or 'association' in h_low:
        return 'pgx'
    if pgx_score >= 2 and gt_score == 0:
        return 'pgx'
    if gt_score >= 1:
        return 'genotype'
    return 'other'


def parse_table(lines: List[str]) -> Optional[Dict[str, Any]]:
    """
    Превращает блок строк таблицы в {kind, headers, rows}.
    kind = 'genotype' | 'pgx' | 'other'
    """
    if len(lines) < 3:
        return None

    headers = _parse_table_cells(lines[0])
    if not headers:
        return None

    kind = _classify_table(headers)

    rows = []
    for line in lines[2:]:
        cells = _parse_table_cells(line)
        if not cells:
            continue
        while len(cells) < len(headers):
            cells.append('')
        cells = cells[:len(headers)]
        rows.append(dict(zip(headers, cells)))

    return {"kind": kind, "headers": headers, "rows": rows}


# ---------- Разбор секции ----------

def parse_section_body(body_lines: List[str]) -> Dict[str, Any]:
    """
    Внутри секции разделяет:
    - tables: обычные таблицы генотипов (kind='genotype')
    - pharmacogenomics: таблицы фармакогенетики (kind='pgx')
    - bullets: пункты списка
    - text: свободный текст
    """
    tables = []
    pharmacogenomics = []
    text_lines = []
    bullets = []

    i = 0
    while i < len(body_lines):
        line = body_lines[i]

        if line.strip().startswith('|'):
            table_lines = []
            while i < len(body_lines) and body_lines[i].strip().startswith('|'):
                table_lines.append(body_lines[i])
                i += 1
            t = parse_table(table_lines)
            if t:
                if t["kind"] == 'pgx':
                    pharmacogenomics.append(t)
                elif t["kind"] == 'genotype':
                    tables.append(t)
                # 'other' — игнорируем
            continue

        m = RE_LIST_ITEM.match(line)
        if m:
            bullets.append(m.group(2).strip())
            i += 1
            continue

        if line.strip():
            text_lines.append(line.strip())
        i += 1

    return {
        "tables": tables,
        "pharmacogenomics": pharmacogenomics,
        "bullets": bullets,
        "text": "\n".join(text_lines).strip(),
    }


# ---------- Разбор гена ----------

def parse_gene_block(gene_num: int, gene_header: str, lines: List[str]) -> Dict[str, Any]:
    sections = []
    current_section = None
    current_body = []
    pre_section_text = []

    for line in lines:
        m = RE_SECTION.match(line.strip())
        if m:
            if current_section is not None:
                parsed = parse_section_body(current_body)
                current_section.update(parsed)
                sections.append(current_section)
            current_section = {
                "code": m.group(1),
                "title": m.group(2).strip(),
            }
            current_body = []
        else:
            if current_section is None:
                if line.strip():
                    pre_section_text.append(line.strip())
            else:
                current_body.append(line)

    if current_section is not None:
        parsed = parse_section_body(current_body)
        current_section.update(parsed)
        sections.append(current_section)

    return {
        "num": gene_num,
        "header": gene_header.strip(),
        "intro": "\n".join(pre_section_text).strip(),
        "sections": sections,
    }


# ---------- Разбор файла ----------

def parse_file(path: str) -> Dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        text = f.read()

    lines = text.split('\n')

    group_title = ""
    intro_lines = []
    genes = []
    interactions_lines = []

    current_gene_num = None
    current_gene_header = ""
    current_gene_lines = []
    mode = "header"

    def flush_gene():
        if current_gene_num is not None:
            genes.append(parse_gene_block(current_gene_num, current_gene_header, current_gene_lines))

    for line in lines:
        stripped = line.rstrip()

        # # Группа N: ... (ВАЖНО: вернуть этот блок, иначе группы не парсятся!)
        if stripped.startswith('# ') and not stripped.startswith('## '):
            flush_gene()
            current_gene_num = None
            group_title = stripped[2:].strip()
            mode = "header"
            continue

        # ## ГЕН N: ...
        m = RE_GENE_HEADER.match(stripped)
        if m:
            flush_gene()
            current_gene_num = int(m.group(1))
            current_gene_header = m.group(2).strip()
            current_gene_lines = []
            mode = "gene"
            continue

        # ИГНОРИРУЕМ заголовки "Дополнительные таблицы" или "ГЕН 1.6"
        if stripped.startswith('## Дополнительные') or stripped.startswith('## ГЕН 1.6'):
            # Просто пропускаем строку, не создавая новый ген
            continue

        # ## Введение: ...
        m = RE_INTRO.match(stripped)
        if m:
            flush_gene()
            current_gene_num = None
            mode = "intro"
            intro_lines.append(m.group(1))
            continue

        # ## Взаимодействия ...
        m = RE_INTERACTION.match(stripped)
        if m:
            flush_gene()
            current_gene_num = None
            mode = "interactions"
            interactions_lines.append(m.group(1))
            continue

        # Наполнение текущего режима
        if mode == "intro":
            if stripped.strip():
                intro_lines.append(stripped.strip())
        elif mode == "gene":
            current_gene_lines.append(stripped)
        elif mode == "interactions":
            if stripped.strip():
                interactions_lines.append(stripped.strip())

    flush_gene()

    interactions = parse_section_body(interactions_lines)

    return {
        "group": group_title,
        "file": os.path.basename(path),
        "intro": "\n".join(intro_lines).strip(),
        "genes": genes,
        "interactions": interactions,
    }


# ---------- Точка входа ----------

def parse_directory(data_dir: str) -> List[Dict[str, Any]]:
    results = []
    for name in sorted(os.listdir(data_dir)):
        if not name.lower().endswith(('.txt', '.md')):
            continue
        path = os.path.join(data_dir, name)
        print(f"Парсинг: {name}")
        results.append(parse_file(path))
    return results


if __name__ == "__main__":
    data_dir = "data"
    out_path = "parsed_knowledge_base.json"
    groups = parse_directory(data_dir)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)
    print(f"\nОбработано групп: {len(groups)}")
    for g in groups:
        print(f"  {g['group']}: {len(g['genes'])} генов")
    print(f"\nРезультат: {out_path}")