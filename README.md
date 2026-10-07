# GENOMIQ-

Парсинг генетических анализов из .docx в JSON и CSV.

## Структура

```
Parsing-Gen/
├── run.py                # точка входа
├── requirements.txt
├── src/genparser/        # код: config, docx_reader, splitter, table_parser, models, exporter, main
├── data/
│   ├── input/            # исходные .docx (analizy.docx)
│   └── output/           # результаты: parsed_genes.json, gene_table_*.csv
└── docs/                 # сайт проекта (genomiq_site.html)
```

## Запуск

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Входной файл положите в `data/input/analizy.docx` (путь задаётся в `src/genparser/config.py`).
#   G E N O M I Q - 
 
 #   G E N O M I Q - 
 
 
