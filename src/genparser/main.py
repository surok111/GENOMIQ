from .docx_reader import extract_text_from_docx
from .splitter import split_into_gene_blocks
from .table_parser import extract_tables_from_block, parse_table
from .models import GeneData, GeneTable
from .exporter import save_to_json, save_to_csv
from . import config
import re
from typing import List


def parse_simple_format(text: str) -> List[GeneData]:
    """
    Парсит текст, где встречаются строки вида:
    Ген: <название>
    Результат: <значение>
    Устойчив к пробелам, разным регистрам и возможным продолжениям результата на нескольких строках.
    """
    genes = []
    lines = text.split('\n')
    current_gene = None
    current_result = None

    # Регулярные выражения для ключевых слов (игнорируют регистр и пробелы вокруг двоеточия)
    gene_pattern = re.compile(r'^\s*Ген\s*:\s*(.*?)\s*$', re.IGNORECASE)
    result_pattern = re.compile(r'^\s*Результат\s*:\s*(.*?)\s*$', re.IGNORECASE)

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Пропускаем пустые строки
        if not line:
            i += 1
            continue

        # Проверяем, не является ли строка записью "Ген: ..."
        gene_match = gene_pattern.match(line)
        if gene_match:
            # Если уже был предыдущий ген, сохраняем его
            if current_gene is not None:
                table = GeneTable(
                    gene_name=current_gene,
                    table_title="Результат анализа",
                    headers=["Ген", "Результат"],
                    rows=[{"Ген": current_gene, "Результат": current_result or ""}]
                )
                genes.append(GeneData(name=current_gene, tables=[table]))

            current_gene = gene_match.group(1).strip()
            current_result = None
            i += 1
            continue

        # Проверяем, не является ли строка записью "Результат: ..."
        result_match = result_pattern.match(line)
        if result_match and current_gene is not None:
            current_result = result_match.group(1).strip()
            i += 1
            continue

        # Если текущий ген уже есть и результат уже начат, то возможно это продолжение результата на следующей строке
        if current_gene is not None and current_result is not None:
            # Добавляем строку к результату, если она не начинается с "Ген:" или "Результат:"
            if not gene_pattern.match(line) and not result_pattern.match(line):
                current_result += " " + line

        i += 1

    # Сохраняем последний найденный ген
    if current_gene is not None:
        table = GeneTable(
            gene_name=current_gene,
            table_title="Результат анализа",
            headers=["Ген", "Результат"],
            rows=[{"Ген": current_gene, "Результат": current_result or ""}]
        )
        genes.append(GeneData(name=current_gene, tables=[table]))

    return genes


def main():
    print("Чтение файла...")
    text = extract_text_from_docx(config.INPUT_FILE)

    # Отладка: посмотрим первые 500 символов (чтобы убедиться, что текст прочитан)
    print("Первые 500 символов файла:")
    print(repr(text[:500]))

    # Пробуем стандартный парсинг (с таблицами)
    print("Попытка стандартного парсинга (таблицы)...")
    gene_blocks = split_into_gene_blocks(text)

    all_genes = []
    for gene_name, block_text in gene_blocks:
        gene = GeneData(name=gene_name)
        first_line = block_text.split('\n')[0].strip()

        raw_tables = extract_tables_from_block(block_text)
        for raw_tbl in raw_tables:
            parsed = parse_table(raw_tbl)
            if parsed and parsed['rows']:
                table = GeneTable(
                    gene_name=gene_name,
                    table_title=first_line,
                    headers=parsed['headers'],
                    rows=parsed['rows']
                )
                gene.tables.append(table)

        if gene.tables:
            all_genes.append(gene)

    # Сохраняем результаты
    if all_genes:
        save_to_json(all_genes, config.OUTPUT_JSON)
        save_to_csv(all_genes, config.OUTPUT_CSV_PREFIX)
        print(f"Обработано генов: {len(all_genes)}")
        print(f"Результаты сохранены в {config.OUTPUT_JSON} и папке data/output/")
    else:
        print("Не удалось найти ни одного гена. Проверьте формат файла.")


if __name__ == "__main__":
    main()