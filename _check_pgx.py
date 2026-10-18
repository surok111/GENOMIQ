import json

with open('parsed_knowledge_base_clean.json', encoding='utf-8') as f:
    data = json.load(f)

print('=== Фармакогенетические таблицы по группам ===')
print()

grand_total = 0
for group in data:
    total_rows = 0
    genes_with_pgx = []
    for gene in group['genes']:
        gene_pgx = 0
        for sec in gene['sections']:
            for tbl in sec.get('pharmacogenomics', []):
                gene_pgx += len(tbl.get('rows', []))
        if gene_pgx:
            name = gene['header'].split('—')[0].strip()
            genes_with_pgx.append(f'{name}({gene_pgx})')
            total_rows += gene_pgx
    if total_rows:
        print(group['group'])
        print(f'  генов: {len(genes_with_pgx)}')
        print(f'  строк: {total_rows}')
        print(f'  гены: {", ".join(genes_with_pgx)}')
        print()
    grand_total += total_rows

print(f'=== ИТОГО строк pgx: {grand_total} ===')