# Environment Audit

Performed: 2026-09-12. Machine: Windows 11 Pro 10.0.26100, x86_64, user `Brian`, shell MINGW64/Git-Bash + PowerShell.

## OS / toolchain

| Tool | Version | Notes |
|---|---|---|
| OS | Windows 11 Pro 10.0.26100 | |
| Shell | MINGW64 (Git Bash) 3.6.9, PowerShell 5.1 | |
| Python | 3.14.2 (`python`/`py`) | Global interpreter; no project venv exists yet for this repo |
| pip (global) | 26.2.1 | Resolved from `H:\Claude\ai-video-factory\.venv` (that project's venv is first on PATH) — **not** a shared environment we should install into |
| Git | 2.55.0.windows.4 | |
| Docker | 29.6.2 (Docker Desktop, `desktop-linux` context) | Running, healthy |
| Docker Compose | v5.3.1 (plugin) | |
| WSL | Not inspected directly — Docker Desktop uses its own `desktop-linux` context, WSL not required for this build | |
| Disk | 48G free of 223G on `C:` | Sufficient |

Global pip packages: only `SQLAlchemy 2.0.52` present — no stray Airflow, Streamlit, dbt, or pandas installs to conflict with. No native Airflow or PostgreSQL install detected outside Docker.

## Existing Docker infrastructure (shared Docker daemon — inspected before creating anything)

Two other unrelated projects already run persistent stacks on this same Docker daemon:

**`H:\Claude\ai-video-factory`** (compose project `ai-video-factory`, running):
- `ai-video-factory-postgres-1` — `pgvector/pgvector:pg16`, host port **5432**, healthy
- `ai-video-factory-redis-1` — `redis:7`, host port **6379**, healthy
- `ai-video-factory-airflow-init-1` — exited (one-shot init container)
- API/worker images built but not currently running

**`H:\Claude\atlas-ai-trading`** (compose project `atlas-ai-trading`, running):
- `atlas-airflow-apiserver` / `atlas-airflow-scheduler` / `atlas-airflow-dag-processor` — custom `atlas-airflow:3.3.1-python3.13` image (built on `apache/airflow:3.3.1-python3.13`), LocalExecutor, FAB auth manager, host port **8080** (apiserver only)
- `atlas-airflow-postgres` — `postgres:16`, Airflow metadata DB only, no host port published
- `atlas-timescaledb` — `timescale/timescaledb:2.17.2-pg16`, host port **5434**, application data
- `atlas-redis` — `redis:7.4-alpine`, created but not started (unrelated to Airflow — used by that project's own live-consumer service)
- `atlas-live-consumer` — running app container

Images already cached locally and reusable without re-pulling: `apache/airflow:3.3.1-python3.13`, `postgres:16`, `redis:7` / `redis:7.4-alpine`.

Networks: `ai-video-factory_default`, `atlas-ai-trading_default`, plus default `bridge`/`host`/`none`. Volumes include `ai-video-factory_postgres_data`, `atlas-ai-trading_airflow_postgres_data`, `atlas-ai-trading_timescaledb_data`, and an unrelated `materials_postgres-db-volume`.

Host ports occupied (verified via `netstat`): **5432, 5434, 6379, 8080**. Free and reserved for this project: **5433** (Postgres), **8081** (Airflow API server), **8501–8504** (one Streamlit dashboard per project).

## Reuse decision

Both existing projects already follow the same pattern independently: **one isolated Docker Compose stack per project**, each with its own Postgres (metadata + app data) and, where needed, its own Airflow, on non-conflicting host ports. Neither shares infrastructure with the other.

This portfolio is a third, unrelated project (data analytics, not trading or video generation). Two options were considered:

1. **Reuse `atlas-ai-trading`'s running Airflow** by mounting new DAGs into its `dags/` folder.
2. **Stand up an isolated stack for this repo**, consistent with the established convention, reusing already-pulled base images (no new downloads) and non-conflicting ports.

**Decision: option 2.** Wiring this portfolio's DAGs into `atlas-ai-trading`'s Airflow would couple two otherwise-independent projects — tearing down or upgrading Atlas's stack would take this portfolio's orchestration down with it, and Atlas's `.env`/connections are scoped to trading data. That violates the spirit of "don't create unnecessary duplicate infrastructure" more than it satisfies it: the existing convention on this machine *is* per-project isolation, so following it is the non-surprising, non-duplicating choice. To keep footprint minimal within that isolated stack: **no separate Redis** (LocalExecutor, same as Atlas, needs none), and **one Postgres 16 instance** serving two logical databases (`airflow` metadata + `analytics` app data with one schema per project) instead of two containers.

No existing installation was deleted, reset, or overwritten. No new Airflow or Postgres user/account was created outside this new isolated stack.
