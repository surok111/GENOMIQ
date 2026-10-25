# GENOMIQ

Интерпретация генетических анализов пациента по базе знаний (8 групп генов) с выдачей HTML/JSON-отчётов.

## Структура

```
GENOMIQ/
├── run.py                 # CLI: build / report
├── app.py                 # веб-интерфейс (streamlit run app.py)
├── requirements.txt
├── src/                   # модули пайплайна
│   ├── md_parser.py       #   data/group*.txt → parsed_knowledge_base.json
│   ├── cleanup.py         #   постобработка → parsed_knowledge_base_clean.json
│   ├── interpreter.py     #   сопоставление генотипов пациента с базой
│   ├── html_report.py     #   HTML-отчёт
│   ├── pdf_parser.py      #   PDF лаборатории → txt
│   ├── analyzer.py        #   анализ базы знаний → reports/analysis_report.*
│   ├── export_for_review.py  # выгрузка базы в Excel для ревью
│   ├── orcid_search.py    #   поиск экспертов по ORCID
│   └── genparser/         #   парсер таблиц генов из .docx
├── data/
│   ├── group1..8_*.txt    # исходные тексты базы знаний
│   ├── parsed_knowledge_base*.json
│   ├── input/             # .docx для genparser
│   └── output/            # результаты genparser
├── samples/               # анализы пациентов (txt/docx/pdf)
├── reports/               # сгенерированные отчёты (orcid/ — выгрузки ORCID)
├── scripts/               # отладочные проверки
└── docs/                  # сайт проекта
```

## Запуск

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python run.py build                         # пересобрать базу знаний
python run.py report samples/test_report.txt
streamlit run app.py
```

Отдельные скрипты (`src/analyzer.py`, `src/export_for_review.py`, `scripts/*.py`) запускаются из корня проекта.
