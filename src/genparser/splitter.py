import re


def split_into_gene_blocks(text: str):
    # Ищем строки, где есть **...** и после может быть двоеточие
    pattern = r'^\*\*(.+?)\*\*.*$'
    lines = text.split('\n')
    blocks = []
    current_gene = None
    current_block = []

    for line in lines:
        match = re.match(pattern, line.strip())
        if match:
            if current_gene:
                blocks.append((current_gene, "\n".join(current_block)))
            current_gene = match.group(1).strip()
            current_block = [line]
        else:
            if current_gene:
                current_block.append(line)
            else:
                # текст до первого заголовка игнорируем
                continue
    if current_gene:
        blocks.append((current_gene, "\n".join(current_block)))
    return blocks