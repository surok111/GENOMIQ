import re
from typing import List, Dict


def extract_tables_from_block(block_text: str):
    """
    Находит все таблицы в тексте блока.
    Таблица – это участок, ограниченный строками, состоящими из '-' или '+'.
    Возвращает список сырых строк таблицы.
    """
    lines = block_text.split('\n')
    tables = []
    in_table = False
    current_table = []

    for line in lines:
        # Признак начала/конца таблицы: строка из множества '-' или '+'
        if re.match(r'^[\s\-+|=]+$', line) and len(line) > 10:
            if not in_table:
                in_table = True
                current_table = [line]
            else:
                current_table.append(line)
                # закрываем таблицу при повторной разделительной строке
                tables.append(current_table)
                current_table = []
                in_table = False
        elif in_table:
            current_table.append(line)
    return tables


def parse_table(raw_lines: List[str]) -> Dict:
    """
    Преобразует строки таблицы в структуру:
    - заголовок (первая строка данных после разделителя)
    - колонки
    - строки данных
    """
    # Убираем пустые строки и лишние пробелы
    lines = [line.strip() for line in raw_lines if line.strip()]
    if len(lines) < 3:
        return {}

    # Первая строка (после верхнего разделителя) – заголовки
    header_line = lines[1]
    headers = [h.strip() for h in header_line.split('|') if h.strip()]

    # Последующие строки до нижнего разделителя – данные
    data = []
    for line in lines[2:-1]:
        if line.startswith('|') or '|' in line:
            cells = [c.strip() for c in line.split('|')]
            # Убираем возможные пустые ячейки по краям, если строка начиналась с |
            if cells and not cells[0]:
                cells = cells[1:]
            if cells and not cells[-1]:
                cells = cells[:-1]
            # Если количество ячеек меньше заголовков, дополняем
            while len(cells) < len(headers):
                cells.append('')
            data.append(dict(zip(headers, cells)))

    return {
        "headers": headers,
        "rows": data
    }