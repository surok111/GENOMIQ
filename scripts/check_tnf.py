import json

with open('data/parsed_knowledge_base_clean.json', encoding='utf-8') as f:
    data = json.load(f)

gene = None
for group in data:
    for g in group['genes']:
        h = g['header']
        if 'TNF' in h and 'TNFSF' not in h and 'TNFR' not in h:
            gene = g
            break
    if gene:
        break

print('Ген:', gene['header'])
print()

for sec in gene['sections']:
    for tbl in sec.get('pharmacogenomics', []):
        print('Секция:', sec['code'], '| заголовки:', tbl['headers'])
        for row in tbl['rows'][:5]:
            sig = row.get('Sig', '')
            assoc = row.get('Association', '')[:90]
            print(f'  Sig={sig!r}  Assoc={assoc!r}')
        print()