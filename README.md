# GENOMIQ

Интерпретация генетических анализов пациента по базе знаний (8 групп генов) с выдачей HTML/JSON-отчётов.

## Структура

```
GENOMIQ/
├── run.py                 # CLI: build / report / sync / backup
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
    │   ├── genparser/         #   парсер таблиц генов из .docx
    │   └── genedb/            #   живая БД генов (OMIM, ClinVar, ClinPGx) + бэкапы
    ├── data/
    │   ├── group1..8_*.txt    # исходные тексты базы знаний
    │   ├── parsed_knowledge_base*.json
    │   ├── genedb/genes.sqlite  # кэш внешних API
    │   ├── backups/           # снимки SQLite + JSON базы знаний
    │   ├── input/             # .docx для genparser
    │   └── output/            # результаты genparser
├── samples/               # анализы пациентов (txt/docx/pdf)
├── reports/               # сгенерированные отчёты (orcid/ — выгрузки ORCID)
├── scripts/               # отладочные проверки
├── docs/                  # сайт проекта
└── gateway/               # API для ЛИС (FastAPI): очередь, статусы, воркер
    ├── app/               #   пакет приложения (uvicorn app.main:app)
    ├── docker-compose.yml #   Postgres + Redis
    └── requirements.txt
```

## Запуск

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python run.py build                         # пересобрать базу знаний
python run.py report samples/test_report.txt
streamlit run app.py

python run.py sync --genes SOD2             # обновить один ген из OMIM/ClinVar/ClinPGx
python run.py sync                          # все гены базы знаний
python run.py db-status
python run.py backup                        # снимок SQLite + JSON
python run.py backup --list
python run.py backup --restore 20261101T083000Z
```

Живая БД хранится в `data/genedb/genes.sqlite`. Перед каждым `sync` автоматически создаётся бэкап в `data/backups/`.

OMIM: при наличии `OMIM_API_KEY` (https://omim.org/api) используется официальный REST; иначе — NCBI Entrez (`db=omim`), которого достаточно для ссылок вида https://omim.org/entry/601769. ClinVar — NCBI E-utilities. ClinPGx — https://api.clinpgx.org/ (лимит 2 запроса/с). Ключи кладутся в `.env` (см. `.env.example`).

Отдельные скрипты (`src/analyzer.py`, `src/export_for_review.py`, `scripts/*.py`) запускаются из корня проекта.

## API Gateway

Код из `genomiq-api-gateway` лежит в `gateway/`. Это приём запросов от лабораторной системы: `POST /v1/genomic-interpretations` ставит задачу в Redis, воркер пишет статус в БД. Веб-интерпретатор (`app.py`, `run.py`) остаётся отдельной точкой входа. Воркер пока отдаёт mock-результат (`USE_MOCK_AI=true`); подключение к `src/interpreter.py` — следующий шаг на этой ветке.

По умолчанию БД — Postgres (`docker compose` в `gateway/`). Redis нужен для очереди и rate limiting. Переопределите `DATABASE_URL` и `RATE_LIMITS` через `.env`.

```
cd gateway
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest
```
