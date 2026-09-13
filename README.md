# Data Analytics Portfolio

Four end-to-end analytics projects sharing one Airflow + Postgres stack. Each project ingests
real (or, where documented, honestly-labeled synthetic) data, validates and transforms it,
loads it into Postgres, computes its analytics in SQL, and serves an interactive Streamlit
dashboard.

| # | Project | Data | Dashboard |
|---|---|---|---|
| 1 | [Climate Risk & Business Impact](projects/01_climate_risk_business_impact/) | Real (Open-Meteo) + synthetic business exposure | http://localhost:8501 |
| 2 | [Dark Store Intelligence](projects/02_dark_store_intelligence/) | Real (UCI Online Retail II) + synthetic store/inventory | http://localhost:8502 |
| 3 | [AI Hiring Bias Detector](projects/03_ai_hiring_bias_detector/) | 100% synthetic (documented bias injection) | http://localhost:8503 |
| 4 | [Fraud Pattern Evolution Tracker](projects/04_fraud_pattern_evolution/) | 100% synthetic (documented fraud-ring injection) | http://localhost:8504 |

See `docs/data_sources.md` for exactly what's real vs. synthetic in each project, and each
project's `docs/methodology_*.md` for formulas, assumptions, and explicit limitations.

## Quick start

```bash
cp .env.example .env
# generate real secrets before first run -- Airflow 3's apiserver refuses to start without them:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # -> AIRFLOW_FERNET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"                                 # -> AIRFLOW_JWT_SECRET
# paste both into .env

docker compose up -d --build postgres airflow-init airflow-apiserver airflow-scheduler airflow-dag-processor
docker compose ps   # confirm airflow-init exited 0, others healthy/starting
```

Airflow UI: http://localhost:8081 (`admin` / whatever `AIRFLOW_ADMIN_PASSWORD` you set in `.env`).

Unpause and run a pipeline:

```bash
docker compose exec airflow-scheduler airflow dags unpause climate_risk_pipeline
docker compose exec airflow-scheduler airflow dags trigger climate_risk_pipeline
docker compose exec airflow-scheduler airflow dags list-runs climate_risk_pipeline
```

DAG ids: `climate_risk_pipeline`, `dark_store_pipeline`, `hiring_bias_pipeline`, `fraud_pattern_pipeline`.

Start a dashboard once its DAG has completed at least one run:

```bash
docker compose up -d --build dashboard-climate     # http://localhost:8501
docker compose up -d --build dashboard-darkstore    # http://localhost:8502
docker compose up -d --build dashboard-hiring       # http://localhost:8503
docker compose up -d --build dashboard-fraud        # http://localhost:8504
```

Shut down (keeps data):

```bash
docker compose down
```

## Repository layout

```
airflow/dags/            one DAG per project
database/init/           first-boot Postgres bootstrap (roles, schemas)
shared/                  ingestion/validation/database helpers used by every DAG
projects/0N_*/           each project's pipeline.py, sql/, dashboard/app.py, data_raw/
docs/                    environment audit, architecture, data sources, methodology per project
```

## Why this architecture

See `docs/environment_audit.md` (what already existed on this machine and why this repo gets its
own isolated Docker stack rather than reusing another project's Airflow) and `docs/architecture.md`
(services, ports, executor choice, data flow, credential handling).

## Power BI

Each project's Postgres schema exposes read-only `*.powerbi_*` views (created by each DAG's
`create_powerbi_views` task) specifically for Power BI — same underlying data as the Streamlit
dashboards, so the two can never disagree. See `docs/powerbi_guide.md` for exact Get Data
connection settings, tables, DAX measures, and page layouts per report, and an honest account of
what was and wasn't verified (Power BI Desktop is installed and confirmed on this machine; a full
interactive GUI build/test was not performed in this session — see that doc for why and what's
left to do).

## Browser testing

All four dashboards were tested with a real headless-Chromium script
(`scripts/browser_test_dashboards.py`, results in `docs/browser_testing.md` and
`scripts/browser_test_screenshots/`) — not just "container started without error." Covers page
load, chart/metric rendering, a real filter interaction, console/JS errors, and a narrow-viewport
render.

## Git / GitHub

This repo is a local git repository with one initial commit; no GitHub remote is configured yet
(that requires a GitHub account/repo this session has no authorization to create). To publish it:

```bash
gh repo create <name> --private --source=. --remote=origin   # or create one on github.com first
git push -u origin master
```

## Troubleshooting

- **Airflow apiserver crashes with `api_auth/jwt_secret must be set!`**: `AIRFLOW_FERNET_KEY` /
  `AIRFLOW_JWT_SECRET` in `.env` are empty — generate real values (commands in Quick start above).
- **`permission denied for schema public` during `airflow db migrate`**: only relevant if you
  changed `database/init/01_init.sh` and recreated the `postgres_data` volume — Postgres 15+ no
  longer grants `CREATE` on `public` to new roles by default; the init script already handles this.
- **A dashboard shows "No data yet"**: its DAG hasn't completed a run yet — trigger it (see Quick
  start) and wait; `dark_store_pipeline` in particular takes ~30-40 minutes end-to-end because it
  parses a real ~45MB/541k-row spreadsheet.
- **Docker Desktop itself becomes unresponsive (`500 Internal Server Error` from `docker ps`)**:
  observed once during this build under heavy concurrent load from multiple unrelated Docker
  Compose projects on the same machine; restarting Docker Desktop resolved it and no data was
  lost (Postgres data lives in a named volume). If a dashboard/Airflow container exited during
  such a crash and didn't auto-restart, `docker compose up -d` again.

## Status

See `PROJECT_STATUS.md` for current build status, bugs found/fixed, and what's left, and
`docs/final_verification_report.md` for the full PASS/FAIL/BLOCKED verification against every
item in this project's definition of done.
