"""
Постобработка parsed_knowledge_base.json:
- убирает '---' из intro/text
- снимает Markdown-разметку **...** из text и bullets
- убирает дублирующийся заголовок 'Введение: ...' из intro
- сохраняет в parsed_knowledge_base_clean.json
"""

import json
import re


RE_BOLD = re.compile(r'\*\*(.+?)\*\*', re.DOTALL)
RE_TRAILING_HR = re.compile(r'\n*---\s*$')
RE_INTRO_HEADER = re.compile(r'^Введение:[^\n]*\n+', re.IGNORECASE)


def strip_bold(s: str) -> str:
    """Убирает **...** из строки, оставляя содержимое."""
    return RE_BOLD.sub(r'\1', s)


def strip_hr(s: str) -> str:
    """Убирает '---' в конце строки."""
    return RE_TRAILING_HR.sub('', s).strip()


def clean_text(s: str) -> str:
    """Полная очистка: bold + hr + trim."""
    if not s:
        return ""
    s = strip_bold(s)
    s = strip_hr(s)
    return s.strip()


def clean_bullet(s: str) -> str:
    """Очистка пункта списка: убирает **, оставляет содержимое."""
    return strip_bold(s).strip()


def clean_intro(s: str) -> str:
    """intro: убирает дублирующийся 'Введение: ...' в начале."""
    if not s:
        return ""
    s = strip_bold(s)
    s = RE_INTRO_HEADER.sub('', s)
    s = strip_hr(s)
    return s.strip()


def clean_section(section: dict) -> dict:
    return {
        "code": section.get("code", ""),
        "title": section.get("title", ""),
        "tables": section.get("tables", []),
        "pharmacogenomics": section.get("pharmacogenomics", []),  # ← новое
        "bullets": [clean_bullet(b) for b in section.get("bullets", [])],
        "text": clean_text(section.get("text", "")),
    }


def clean_gene(gene: dict) -> dict:
    return {
        "num": gene.get("num"),
        "header": gene.get("header", ""),
        "intro": clean_text(gene.get("intro", "")),
        "sections": [clean_section(s) for s in gene.get("sections", [])],
    }


def clean_interactions(inter: dict) -> dict:
    return {
        "tables": inter.get("tables", []),
        "bullets": [clean_bullet(b) for b in inter.get("bullets", [])],
        "text": clean_text(inter.get("text", "")),
    }


def clean_group(group: dict) -> dict:
    return {
        "group": group.get("group", ""),
        "file": group.get("file", ""),
        "intro": clean_intro(group.get("intro", "")),
        "genes": [clean_gene(g) for g in group.get("genes", [])],
        "interactions": clean_interactions(group.get("interactions", {})),
    }


def main():
    src = "parsed_knowledge_base.json"
    dst = "parsed_knowledge_base_clean.json"

    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    cleaned = [clean_group(g) for g in data]

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    # немного статистики для контроля
    genes_total = sum(len(g["genes"]) for g in cleaned)
    sections_total = sum(
        len(gene["sections"]) for g in cleaned for gene in g["genes"]
    )
    print(f"Групп: {len(cleaned)}")
    print(f"Генов: {genes_total}")
    print(f"Секций: {sections_total}")
    print(f"Результат: {dst}")


if __name__ == "__main__":
    main()