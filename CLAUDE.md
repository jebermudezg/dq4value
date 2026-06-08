# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**DQ4Value** — a data quality analysis platform. Users upload CSV/Excel datasets, configure which data quality dimensions to evaluate per column, run analysis, and get a score (0–100), an issues list, an Excel report, and a self-contained HTML dashboard. The frontend is a single-page HTML file; the backend is FastAPI + SQLite.

## Commands

```bash
# Start the dev server (from project root)
python3 -m uvicorn api.main:app --reload --port 8000

# Run all tests
python3 -m pytest tests/ -v

# Run a single test file
python3 -m pytest tests/test_dimensiones.py -v

# Run a single test by name
python3 -m pytest tests/test_dimensiones.py::TestCompletitud::test_happy_path -v

# End-to-end API test (server must be running)
python3 tests/prueba_presentacion.py
python3 tests/prueba_integral_final.py

# Check syntax of the inline JS in the frontend (no build step)
node -e "
const fs=require('fs'),html=fs.readFileSync('frontend/index.html','utf8');
const m=html.match(/<script>\s*([\s\S]*?)\s*<\/script>\s*<\/body>/);
try{new Function(m[1]);console.log('OK');}catch(e){console.log('Error:',e.message);}
"
```

The default admin account is `admin@dqplatform.com` / `Admin123!` (created on first startup by `init_db()`).

## Architecture

### Request flow for a full analysis

```
Browser (frontend/index.html)
  │
  ├─ POST /upload          → stores DataFrame in _file_store[file_id]
  │                          saves raw file to temp_files/
  ├─ GET  /profile/{id}    → engine/profiler.py → column stats + masks
  ├─ POST /ai/suggest      → ai/claude_analyzer.py → rule-based dim suggestions
  ├─ POST /analyze         → engine/scorer.py (DQScorer)
  │                          → engine/report_gen.py  → reports/<user>/<YYYY-MM>/<ts>_<name>.xlsx
  │                          → engine/dashboard_gen.py → reports/…_dashboard.html
  │                          → DB: INSERT INTO analisis (stores paths)
  │                          ⚠️  _file_store[file_id] is DELETED after /analyze completes
  └─ GET  /issues/{id}     → reads from _analysis_store[file_id] (still in memory)
```

### Key in-memory stores (api/main.py)

- `_file_store[file_id]` — `{"df": DataFrame, "original_name": str, "col_info": [...]}`. **Cleared after `/analyze`** — any endpoint that needs the raw file must be called before analyze.
- `_analysis_store[file_id]` — full results dict from `DQScorer.run_analysis()` including the `issues_df` DataFrame. Survives the analyze call, used by `/issues/{file_id}`.
- `_progress_store[file_id]` — `{pct, message, done, error}` — polled by frontend via `GET /analyze/status/{file_id}`.

### Engine layer

**`engine/scorer.py` — `DQScorer`**
- `configure(column, dims_config)` → chainable
- `run_analysis()` → `{scores_por_columna, score_general, issues_df, total_registros, total_problemas}`
- `compute_summary(results)` → adds `pct_limpios`, `peor_dimension` to the results dict
- Each dimension runs in a `ThreadPoolExecutor(max_workers=1)` with a **30-second timeout**. Timed-out dimensions get `score=0.0` and empty issues.

**`engine/dimensions/`** — one file per dimension, uniform signature:
```python
def check_<dim>(df, id_col, target_col, **params) -> tuple[float, pd.DataFrame]
```
The returned `issues_df` always has columns: `[id_col, "columna", "dimension", "descripcion", "valor_encontrado"]`.

**`engine/dimensions/similitud.py`** — most complex. Uses Jaro-Winkler (jellyfish), TF-IDF cosine, and a custom Affine Gap alignment (`_brecha_afin`). Has early-exit optimizations (length ratio < 0.4, max 50-char truncation, pair cap at 15,000). Supports algorithms: `jaro_winkler`, `brecha_afin`, `tfidf`.

**`engine/profiler.py`** — returns per-column stats, data masks (`mask()` + `drill_through()`), and alerts. All individual calculations are wrapped in try/except so partial failures don't break the whole profile.

**`engine/dashboard_gen.py`** — generates a self-contained HTML file (no external dependencies except font stack). Uses plain strings with `%%PLACEHOLDER%%` markers (not f-strings) to avoid escaping CSS `{}`. Key function: `generate_dashboard_html(analysis_results, filename, fecha, etiqueta, descripcion)`.

### Database (SQLite)

`database/db.py` — `init_db()` creates/migrates tables on startup. New columns are added via `ALTER TABLE … ADD COLUMN` inside try/except (idempotent). Access rows as `dict(row).get("field")` to avoid KeyError when a column may not exist in old rows.

Tables: `usuarios`, `sesiones`, `analisis`.

Report files are stored on disk under `reports/<username>/<YYYY-MM>/`. Paths relative to project root are stored in `analisis.ruta_reporte` and `analisis.ruta_dashboard`.

### Frontend (frontend/index.html)

Single-file SPA — all HTML, CSS, and JS in one file (~4,900 lines). No build step.

**`frontend/config.js`** — sets `API_BASE` to the production Railway URL. For local dev the frontend makes requests to `http://127.0.0.1:8000` when opened as `file://` on localhost — check `config.js` if API calls are going to the wrong host.

Key JS globals:
- `state` — `{fileId, columns, analysisResult, perfil, uploadedFilename, _etiqueta, _dimAvg, _dimsSorted}`
- `allIssues` — flat array of issue objects, populated after `/issues/{fileId}`
- `_file_store` is cleared server-side after analyze, so `/profile/{id}/export` must be called **before** `/analyze`

Key JS functions:
- `buildResultsScreen(data)` — populates the step-4 results screen from `data` (analyze response + `compute_summary` fields). Computes per-dimension averages from `scores_por_columna`, updates gauge SVG via `stroke-dashoffset = 452.39 * (1 - score/100)`, renders dim bars, KPIs, and column cards.
- `renderDonutAndRemed(issues, dimAvg, dimsSorted)` — renders issue bars (left panel), issue count list (right panel), and top-3 remediation cards. Called from `fetchAndRenderIssues()`.
- `openCurrentDashboard()` → fetches latest historial entry → `openHistDashboard(id)` → blob URL in new tab.

### Colour palette (unified — apply everywhere)

| State | Text/bar | Background | On-bg text |
|-------|----------|-----------|------------|
| ≥ 80 (good) | `#16A34A` | `#DCFCE7` | `#166534` |
| 60–79 (amber) | `#B45309` | `#FEF3C7` | `#92400E` |
| < 60 (critical) | `#DC2626` | `#FEE2E2` | `#991B1B` |

**Never use `#D97706`, `#FEF9C3`, or `#854D0E`** — these are the old amber values that were replaced.

### Gauge SVG formula

```js
const circumference = 452.39;  // 2π × r=72
const dashoffset = circumference * (1 - score / 100);
// arc element: stroke-dasharray="452.39 452.39", transform="rotate(-90 90 90)"
```

### Auth

Token-based. `Authorization: Bearer <token>` header on all protected endpoints. Tokens stored in `sesiones` table with expiry. `get_current_user()` and `require_admin()` are the two auth guards in `api/main.py`.

## Deployment

Hosted on Railway. `Procfile` / `nixpacks.toml` both run:
```
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```
Production URL: `https://dq4value-production.up.railway.app`  
GitHub repo: `https://github.com/jebermudezg/dq4value`

`frontend/config.js` points to the production API — change it to `http://127.0.0.1:8000` for local development.

## Test structure

| File | What it tests |
|------|---------------|
| `tests/test_dimensiones.py` | Unit tests for all 11 dimension functions + `DQScorer` |
| `tests/test_api.py` | Integration tests via `TestClient` (no running server needed) |
| `tests/test_e2e.py` | Full user flow through `TestClient` |
| `tests/test_carga.py` | Performance tests (dataset_1000 < 60s, etc.) |
| `tests/test_engine.py` | Profiler + suggest_dimensions_rules |
| `tests/test_mascaras.py` | Data masking functions |
| `tests/prueba_presentacion.py` | 40-point live API test (server must be running) |
| `tests/prueba_integral_final.py` | 36-point live API test with content checks on generated HTML |
| `tests/dataset_1000.csv` | Standard test dataset (1,000 rows, 12 columns) |
