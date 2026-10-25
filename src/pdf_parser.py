"""
pdf_parser.py — извлекает гены из PDF-отчётов лабораторий.

Читает PDF → извлекает строки вида:
    <номер> <ГЕН> <вариант> <генотип>
    <номер> <ГЕН> null норма

Сохраняет в .txt в формате:
    Ген: XXX
    Результат: YYY

Использование:
    python src/pdf_parser.py samples/onko.pdf
    python src/pdf_parser.py samples/onko.pdf -o samples/onko.txt
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("❌ Нужен pdfplumber. Установите: pip install pdfplumber")
    sys.exit(1)


# ============================================================
#  Чистка текста
# ============================================================

def clean_text(text: str) -> str:
    """Убирает невидимые символы PDF."""
    if not text:
        return ""
    # Все виды невидимых пробелов
    for ch in ('\u200b', '\u200c', '\u200d', '\ufeff', '\u00a0',
               '\u2000', '\u2001', '\u2002', '\u2003', '\u2004',
               '\u2005', '\u2006', '\u2007', '\u2008', '\u2009',
               '\u200a', '\u202f', '\u205f', '\u3000'):
        text = text.replace(ch, ' ')
    # Схлопываем кратные пробелы
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text


def read_pdf(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        pages = []
        for page in pdf.pages:
            t = page.extract_text() or ""
            pages.append(t)
        return "\n".join(pages)


# ============================================================
#  Нормализация генотипов
# ============================================================

CYR_TO_LAT = str.maketrans({
    'С': 'C', 'с': 'c',
    'Т': 'T', 'т': 't',
    'А': 'A', 'а': 'a',
    'G': 'G', 'g': 'g',
    'Г': 'G', 'г': 'g',
})


def normalize_gt(raw: str) -> str:
    """'A A' → 'AA', 'G/A' → 'GA', 'С С' → 'CC'."""
    gt = raw.replace(' ', '').replace('/', '').replace('|', '').strip()
    gt = gt.translate(CYR_TO_LAT)
    return gt.upper()


# ============================================================
#  Парсинг PDF-таблицы «Лаб-ДНК»
# ============================================================

# Строки с "норма": "4 GSTM1 null норма"
RE_NORMA = re.compile(
    r'(\d{1,3})\s+(GSTM1|GSTT1|GSTТ1)\s+null\s+(норма|нормальн\w*)',
    re.IGNORECASE,
)

# Разорванный формат: "GSTТ1 null\n5 норма"
# Ген и номер+норма на разных строках
RE_NORMA_SPLIT = re.compile(
    r'(GST[ТT]1)\s+null\s*\n\s*(\d{1,3})\s+(норма|нормальн\w*)',
    re.IGNORECASE,
)

# Формат: <номер> <ГЕН> <вариант> <генотип>
# Примеры:
#   1 CYP1A1 Ile462Val (A>G)     A A
#   6 GSTP1 Ile105Val А>G        А G
#   8 NAT2 G590A (rs1799930)     G A
#   12 TP53 Pro72Arg G >С        G C
#   2 CYP2C9 430С>Т (rs1799853)  С С
RE_ROW = re.compile(
    r'^\s*(\d{1,3})\s+'                              # номер
    r'(CYP\d[A-Z0-9]+|GST[A-Z0-9]+|GSTТ\d|NAT\d|TP53|ТP53)\s+'  # ген
    r'(.+?)\s+'                                       # вариант (ленивый)
    r'([A-ZА-ЯСT]{1,2}(?:\s+[A-ZА-ЯСT]{1,2})?)\s*$',  # генотип
    re.MULTILINE | re.IGNORECASE,
)

# Формат, где ген и генотип на разных строках:
#   "CYP1A1 Ile462Val (A>G)" на одной строке
#   "1 A A" на следующей
RE_GENE_LINE = re.compile(
    r'^\s*(CYP\d[A-Z0-9]+|GST[A-Z0-9]+|GSTТ\d|NAT\d|TP53|ТP53)\s+(.+?)\s*$',
    re.IGNORECASE,
)

RE_NUM_GT_LINE = re.compile(
    r'^\s*(\d{1,3})\s+([A-ZА-ЯСT]{1,2}(?:\s+[A-ZА-ЯСT]{1,2})?)\s*$',
    re.MULTILINE,
)


def parse_lab_dnk(text: str) -> list[dict]:
    """
    Возвращает список {gene, result}.
    Формат: <номер> <ГЕН> <вариант> <генотип>
    Плюс отдельно ловит GSTT1 с "норма" на следующей строке.
    """
    results = []
    seen = set()

    # 1) Строки "GSTM1 null норма" / "GSTT1 null норма" (всё на одной строке)
    for m in RE_NORMA.finditer(text):
        gene = m.group(2).upper().replace('GSTТ', 'GSTT')  # кир. Т → лат. T
        key = (gene, "норма")
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "gene": gene,
            "result": "норма (non-null)",
        })

    # 2) Разорванный формат: "GSTТ1 null\n5 норма"
    for m in RE_NORMA_SPLIT.finditer(text):
        gene = 'GSTT1'  # всегда латиница в итоге
        key = (gene, "норма")
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "gene": gene,
            "result": "норма (non-null)",
        })

    # 3) Строки, где всё в одной строке
    for m in RE_ROW.finditer(text):
        gene = m.group(2).upper().replace('GSTТ', 'GSTT').replace('ТP53', 'TP53')
        variant = m.group(3).strip()
        gt_raw = m.group(4).strip()
        gt = normalize_gt(gt_raw)

        if gene in ('GSTM1', 'GSTT1'):
            continue
        if len(gt) < 2 or len(gt) > 2:
            continue
        if not re.match(r'^[ACGT]{2}$', gt):
            continue

        key = (gene, gt, variant)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "gene": gene,
            "result": f"{variant} → {gt}",
        })

    return results


def parse_alternative_format(text: str) -> list[dict]:
    """
    Альтернативный формат, где строки разорваны:
        CYP1A1 Ile462Val (A>G)
        1 A A
    """
    lines = text.split('\n')
    results = []
    seen = set()

    last_gene = None
    last_variant = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Строка с геном
        m = RE_GENE_LINE.match(line)
        if m:
            last_gene = m.group(1).upper().replace('GSTТ', 'GSTT').replace('ТP53', 'TP53')
            last_variant = m.group(2).strip()
            continue

        # Строка с номером и генотипом: "1 A A"
        m = RE_NUM_GT_LINE.match(line)
        if m and last_gene:
            num = m.group(1)
            gt_raw = m.group(2)
            gt = normalize_gt(gt_raw)

            if last_gene in ('GSTM1', 'GSTT1'):
                last_gene = None
                last_variant = None
                continue
            if len(gt) != 2 or not re.match(r'^[ACGT]{2}$', gt):
                last_gene = None
                last_variant = None
                continue

            key = (last_gene, gt, last_variant)
            if key not in seen:
                seen.add(key)
                results.append({
                    "gene": last_gene,
                    "result": f"{last_variant} → {gt}",
                })

            last_gene = None
            last_variant = None

    return results


# ============================================================
#  Сохранение в наш формат
# ============================================================

def save_as_txt(genes: list[dict], out_path: str):
    lines = []
    for g in genes:
        lines.append(f"Ген: {g['gene']}")
        lines.append(f"Результат: {g['result']}")
        lines.append("")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")


# ============================================================
#  main
# ============================================================

def parse_pdf(path: str) -> list[dict]:
    print(f"Чтение: {path}")
    text = clean_text(read_pdf(path))
    print(f"Прочитано символов: {len(text)}")

    # Пробуем ОБА парсера и объединяем
    genes_main = parse_lab_dnk(text)
    print(f"Парсер 1 (строки с номером): {len(genes_main)} генов")

    genes_alt = parse_alternative_format(text)
    print(f"Парсер 2 (разорванные строки): {len(genes_alt)} генов")

    # Объединяем, убираем дубли
    all_genes = []
    seen = set()
    for g in genes_main + genes_alt:
        key = (g["gene"], g["result"])
        if key in seen:
            continue
        seen.add(key)
        all_genes.append(g)

    print(f"Всего уникальных: {len(all_genes)}")
    return all_genes


def main():
    parser = argparse.ArgumentParser(
        prog="pdf_parser.py",
        description="Извлекает гены из PDF-отчёта и сохраняет в наш .txt формат.",
    )
    parser.add_argument("pdf", help="Путь к PDF-файлу")
    parser.add_argument("-o", "--output", default=None,
                        help="Путь к выходному .txt (по умолчанию: <pdf>_parsed.txt)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"❌ Файл не найден: {pdf_path}")
        sys.exit(1)

    genes = parse_pdf(str(pdf_path))

    if not genes:
        print("❌ Не удалось извлечь ни одного гена.")
        print("\nСырой текст (первые 2000 символов):")
        text = clean_text(read_pdf(str(pdf_path)))
        print(text[:2000])
        sys.exit(2)

    # Куда сохраняем
    if args.output:
        out_path = args.output
    else:
        out_path = pdf_path.with_name(pdf_path.stem + "_parsed.txt")

    save_as_txt(genes, out_path)
    print(f"\n💾 Сохранено: {out_path}")
    print("\nСодержимое:")
    print("-" * 40)
    for g in genes:
        print(f"  {g['gene']:10} → {g['result']}")


if __name__ == "__main__":
    main()