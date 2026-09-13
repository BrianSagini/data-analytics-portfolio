# Architecture

## Component diagram

```
                         ┌─────────────────────────────┐
                         │   Airflow 3.3.1 (LocalExec)  │
                         │  apiserver + scheduler +     │
                         │  dag-processor + init        │
                         │  (custom image, this repo's  │
                         │   Dockerfile, host :8081)    │
                         └──────────────┬───────────────┘
                                        │ orchestrates
              ┌─────────────┬───────────┼───────────┬─────────────┐
              ▼             ▼           ▼            ▼             ▼
     climate_risk_    dark_store_  hiring_bias_  fraud_pattern_
     pipeline DAG     pipeline DAG pipeline DAG  pipeline DAG
              │             │           │            │
              ▼             ▼           ▼            ▼
        ┌───────────────────────────────────────────────────┐
        │   shared/ (ingestion, validation, transformations, │
        │   database helpers) — imported by every DAG        │
        └──────────────────────┬────────────────────────────┘
                                ▼
                 ┌───────────────────────────────┐
                 │  Postgres 16 (host :5433)      │
                 │  DB "airflow"  — metadata only │
                 │  DB "analytics" — schemas:     │
                 │    climate_risk, dark_store,   │
                 │    hiring_bias, fraud_pattern  │
                 └───────────────┬────────────────┘
                                 │ read
              ┌──────────────────┼──────────────────┬──────────────────┐
              ▼                  ▼                  ▼                  ▼
     Streamlit :8501    Streamlit :8502    Streamlit :8503    Streamlit :8504
     Climate Risk        Dark Store         Hiring Bias        Fraud Pattern
     dashboard           dashboard          dashboard          dashboard
```

## Services & ports

| Service | Image | Host port | Purpose |
|---|---|---|---|
| `airflow-postgres` | `postgres:16` (reused, already local) | 5433 | Airflow metadata (`airflow` DB) + analytics data (`analytics` DB, one schema per project) |
| `airflow-init` | built from `airflow/Dockerfile` | — | One-shot: migrate DB, create admin user (idempotent — checks first) |
| `airflow-apiserver` | built from `airflow/Dockerfile` | 8081 | Airflow 3.x webserver/API |
| `airflow-scheduler` | built from `airflow/Dockerfile` | — | Schedules/executes DAGs (LocalExecutor) |
| `airflow-dag-processor` | built from `airflow/Dockerfile` | — | Parses DAGs (Airflow 3.x split-role architecture) |
| `dashboard-climate` | `python:3.12-slim` + streamlit | 8501 | Project 1 dashboard |
| `dashboard-darkstore` | `python:3.12-slim` + streamlit | 8502 | Project 2 dashboard |
| `dashboard-hiring` | `python:3.12-slim` + streamlit | 8503 | Project 3 dashboard |
| `dashboard-fraud` | `python:3.12-slim` + streamlit | 8504 | Project 4 dashboard |

No Redis/Celery: LocalExecutor is sufficient at this workload (4 lightweight DAGs, daily/on-demand schedules) — matches the pattern already used by `atlas-ai-trading`'s Airflow, avoiding unneeded infrastructure.

## Executor & auth

- Executor: `LocalExecutor`
- Auth manager: `FabAuthManager` (Airflow 3.x default-compatible, simple username/password admin)
- Airflow admin user is created idempotently by `airflow-init` (checks `airflow users list` before creating)

## Data flow (per project)

1. **Extract** — Python task calls a public API (Open-Meteo, UCI archive) or generates/loads a documented synthetic dataset; raw payload saved under `projects/<n>/data_raw/` (bind-mounted) with a timestamp, never overwritten in place.
2. **Validate** — schema/range checks (`shared/validation`); failures are logged and quarantined, not silently dropped.
3. **Transform** — pandas-based cleaning + feature engineering (`shared/transformations`), idempotent (re-running a DAG for the same logical date replaces that partition, not append-blindly).
4. **Load** — upsert into that project's Postgres schema (`shared/database`), via `ON CONFLICT DO UPDATE` on natural keys.
5. **Analytical SQL** — views/materialized tables built with plain SQL in `projects/<n>/sql/`, run as a DAG task.
6. **Dashboard** — Streamlit app queries the `analytics` DB directly (read-only role), never recomputes business logic that SQL already owns.

## Project structure

See repo root listing (`README.md`) — top-level: `airflow/`, `database/`, `shared/`, `projects/01..04/`, `docs/`.

## Credential management

- All secrets read from environment variables via `.env` (git-ignored), templated in `.env.example`.
- No API key is required for any of the four projects' primary data sources (see `docs/data_sources.md`) — this was verified live, not assumed.
- Airflow Connections are used only if a future optional data source needs one; none are hardcoded in DAG files.
- Postgres roles: one read-write role for the ETL/Airflow user, one read-only role for dashboards (least privilege).

## Startup / shutdown

```bash
# from repo root, after `cp .env.example .env`
docker compose up -d --build      # start Postgres + Airflow (init runs once and exits 0)
docker compose ps                  # confirm airflow-init exited 0, others healthy
docker compose logs -f airflow-init  # first-run troubleshooting

# dashboards (run locally against the container's published Postgres port, not in Compose,
# so they can be iterated on without a rebuild — see docs/deployment.md)
docker compose down                # stop everything, keep volumes (no -v)
```

## Reuse decisions carried over from the environment audit

- Isolated stack, not wired into `atlas-ai-trading`'s Airflow (see `docs/environment_audit.md`).
- Base images (`apache/airflow:3.3.1-python3.13`, `postgres:16`) reused from local cache, not re-pulled.
- Host ports chosen to avoid the 5432/5434/6379/8080 already in use by the other two projects.
