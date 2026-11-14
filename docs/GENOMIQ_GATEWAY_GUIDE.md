# GenomIQ + API Gateway — instructions for you

This repository is **two products in one tree**:

| Part | Folder | Purpose |
|------|--------|---------|
| **GenomIQ (main product)** | repo root | Knowledge base, CLI, Streamlit UI, HTML reports |
| **API Gateway (LIS integration)** | `gateway/` | FastAPI, Redis queue, worker, rate limits, mock AI, FHIR Bundle |

The old standalone project `C:\genomiq-api-gateway` is **not** the source of truth anymore — use `C:\CParsing-Gen\gateway\`.

---

## 1. Significant files (what to open when something breaks)

### GenomIQ (root)

| File | What it does |
|------|----------------|
| `run.py` | CLI: `build`, `report`, `sync`, `backup` |
| `app.py` | Streamlit web UI |
| `requirements.txt` | Dependencies for the interpreter / Streamlit |
| `src/interpreter.py` | Match patient genotypes to knowledge base |
| `src/html_report.py` | Generate HTML reports |
| `src/genedb/` | Live gene DB (OMIM, ClinVar, ClinPGx) |
| `data/parsed_knowledge_base_clean.json` | Clean knowledge base used at report time |
| `samples/` | Example patient reports |
| `reports/` | Generated outputs |

### API Gateway (`gateway/`)

| File | What it does |
|------|----------------|
| `app/main.py` | FastAPI app, lifespan (DB + Redis + **worker**), CORS, rate limit middleware |
| `app/api/endpoints.py` | `POST /v1/genomic-interpretations`, `GET /v1/status/{task_id}`, `/health` |
| `app/core/config.py` | Settings: `DATABASE_URL`, `REDIS_URL`, `USE_MOCK_AI`, `RATE_LIMITS` |
| `app/core/rate_limiter.py` | Per–API-key token bucket (`X-API-Key`, `X-RateLimit-*`) |
| `app/core/redis_client.py` | Redis client + queue names (`genomic_queue`, `dead_letter_queue`) |
| `app/db/models.py` | `TaskRecord` (status, attempts, `result` JSON — no PHI in columns except result when done) |
| `app/db/session.py` | Async SQLAlchemy engine (SQLite locally, Postgres if you set `DATABASE_URL`) |
| `app/workers/task_worker.py` | Consumes queue → mock AI → **FHIR Bundle** → saves to DB |
| `app/services/mock_ai_service.py` | MTHFR C677T mock (substring match `CT` / `TT` / `CC` in `raw_data`) |
| `app/services/dependencies.py` | `get_ai_service()` — mock vs real (real not implemented) |
| `app/services/fhir_mapper.py` | `build_fhir_bundle()` — FHIR R4 genomics collection Bundle |
| `app/core/logging.py` | JSON logs; redacts PHI keys (`raw_data`, `patient_reference`, …) |
| `app/core/telemetry.py` | Traces, `X-Request-ID`, request-duration histogram, FHIR failure counter |
| `app/schemas/genomic.py` | Request body: `patient_reference`, `raw_data`, `callback_url`, … |
| `docker-compose.yml` | Optional Postgres + Redis (production-style); **not required** for local SQLite |
| `requirements.txt` | Gateway deps (`fhir.resources`, `aiosqlite`, `fakeredis` for tests, …) |
| `genomiq.db` | Local SQLite DB (created on start; gitignored) |

### Tests (`gateway/tests/`)

| File | Covers |
|------|--------|
| `test_rate_limiter.py` | Milestone 3 — API keys, 429, headers |
| `test_mock_ai.py` | Milestone 4 — mock genotypes |
| `test_worker.py` | Worker happy path, retries, DLQ |
| `test_endpoint_di.py` | Endpoint resolves AI service but does **not** call it inline |
| `test_fhir_mapper.py` | Milestone 5 — FHIR Bundle structure and links |
| `conftest.py` | `fakeredis` + per-test SQLite file for worker tests |

---

## 2. How to run the system

### A. GenomIQ interpreter (no gateway)

From repo root `C:\CParsing-Gen`:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

python run.py build
python run.py report samples\test_report.txt
streamlit run app.py
```

### B. API Gateway (local dev)

**You need Redis** (Memurai on Windows or `redis-server`). Default: `redis://localhost:6379/0`.

**Database:** default is **SQLite** (`gateway/genomiq.db`). No Postgres required.

```powershell
cd C:\CParsing-Gen\gateway

# Use an existing venv if you have one, e.g.:
# C:\genomiq-api-gateway\venv\Scripts\activate
pip install -r requirements.txt

# From gateway/ (so app package resolves):
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**If startup still hits Postgres:** check `gateway/.env` — remove or override:

```env
DATABASE_URL=sqlite+aiosqlite:///./genomiq.db
REDIS_URL=redis://localhost:6379/0
USE_MOCK_AI=true
```

### C. Try the API (PowerShell)

```powershell
$body = @{
  patient_reference  = "Patient/demo-1"
  specimen_reference = "Specimen/demo-1"
  raw_data           = "rs1801133:CT"
  callback_url       = "https://example.org/callback"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/genomic-interpretations" `
  -Body $body -ContentType "application/json" `
  -Headers @{ "Idempotency-Key" = "demo-$(Get-Random)" }

# Poll status (use task_id from Location header):
# GET http://127.0.0.1:8000/v1/status/<task_id>
```

When `status` is `completed`, `result` is a **FHIR Bundle** (`resourceType: Bundle`, `type: collection`), not the flat mock dict.

**Demo `raw_data` values:** `CT`, `TT`, `CC`, or `rs1801133:TT`. Strings like `ACGT` fail (permanent task failure).

Optional rate-limit tiers (Milestone 3): header `X-API-Key: api_key_lab_a` (if defined in `RATE_LIMITS` in config).

### D. Run all gateway tests (no Docker)

```powershell
cd C:\CParsing-Gen\gateway
python -m pytest -q
```

Expect on the order of **40+ passed** (rate limit + mock AI + worker + FHIR).

---

## 3. What changed over the milestones (quick memory aid)

| Milestone | Branch (historical) | What was added |
|-----------|---------------------|----------------|
| Unite | `unite/genomiq-api-gateway` | `gateway/` copied into GENOMIQ repo |
| 3 | `feature/gateway-milestone-3-rate-limit` | `rate_limiter.py`, enabled in `main.py`, `test_rate_limiter.py` |
| 4 | `feature/gateway-milestone-4-mock-ai` | `app/services/*`, worker calls mock AI, endpoint DI stub |
| 4b (local) | same branch | SQLite default in `config.py` / `session.py` |
| 5 | on top of M4 | `fhir_mapper.py`, worker stores FHIR Bundle in `result`, `test_fhir_mapper.py` |
| 6 | same working tree | `logging.py`, `telemetry.py`, trace context on the Redis message, `correlation_id` on the task |

**Important behavior change (M5):** `GET /v1/status/{id}` → `result` is a **FHIR R4 Bundle**, not `{ "gene": "MTHFR", ... }`.

**Important demo change (M4):** use genotypes in `raw_data`, not `ACGT` or old `FORCE_FAIL`.

---

## 4. How to see what changed (Git / GitHub)

From `C:\CParsing-Gen`:

```powershell
git branch -a
git status

# Everything in gateway/ compared to old local main:
git diff main...HEAD --stat

# Only gateway folder:
git diff main...HEAD -- gateway/

# Uncommitted work (your working tree):
git diff
git diff --stat

# Commits on your branch not on origin/main:
git fetch origin
git log origin/main..HEAD --oneline
```

**Remote:** `https://github.com/surok111/GENOMIQ` — `origin/main` already has unite + rate limiting (M3). Milestone 4/5/SQLite/FHIR may still be only on your local branch until you commit and push.

**Stash:** `git stash list` — old Streamlit/report edits from before unite (`stash@{0}`), unrelated to gateway.

---

## 5. Cursor / IDE cheat sheet

1. **Explorer** → expand `gateway/app/` for API; root `src/` for interpreter.
2. **Source Control** → see modified files and diffs.
3. **Branch** (status bar) → switch between `main`, `feature/gateway-milestone-4-mock-ai`, etc.
4. Open **`gateway/app/api/endpoints.py`** when changing HTTP contract.
5. Open **`gateway/app/workers/task_worker.py`** when changing async processing / FHIR save.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Connection refused` port 5432 | Old Postgres `DATABASE_URL` | Use SQLite default or fix `.env` |
| Redis / queue 503 | Redis not running | Start Memurai / Redis on 6379 |
| Task `failed`, attempt 1 | Unknown `raw_data` | Use `CT` / `TT` / `CC` in string |
| Tests fail on import `fhir` | Deps not installed | `pip install -r gateway/requirements.txt` |
| `POST` 500, `USE_MOCK_AI=false` | Real AI not implemented | Keep `USE_MOCK_AI=true` locally |

---

## 7. One-line mental model

**Root** = offline/clinical report pipeline for your knowledge base. **`gateway/`** = async LIS API: accept JSON → queue → mock interpret → **FHIR Bundle** in DB → client polls status.

Keep this file open when you return after a break; update the milestone table when you merge new work.
