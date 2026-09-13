# Deployment / Operations

## Services & ports (recap of `docs/architecture.md`)

| Service | Host port |
|---|---|
| Postgres | 5433 |
| Airflow API server (UI) | 8081 |
| Dashboard — Climate Risk | 8501 |
| Dashboard — Dark Store | 8502 |
| Dashboard — Hiring Bias | 8503 |
| Dashboard — Fraud Pattern | 8504 |

Chosen to avoid the 5432/5434/6379/8080 already used by two other unrelated local Docker
projects on this machine (`ai-video-factory`, `atlas-ai-trading`) — see `docs/environment_audit.md`.

## Bring up

```bash
cp .env.example .env   # then generate & paste AIRFLOW_FERNET_KEY / AIRFLOW_JWT_SECRET, see README

docker compose up -d --build postgres airflow-init airflow-apiserver airflow-scheduler airflow-dag-processor
docker compose ps
```

`airflow-init` is a one-shot container (migrates the Airflow metadata DB, creates the admin user
idempotently) — it should show `Exited (0)`, not `Up`. If it exits non-zero, `docker compose logs
airflow-init` first.

Bring dashboards up individually once their DAG has run at least once:

```bash
docker compose up -d --build dashboard-climate dashboard-darkstore dashboard-hiring dashboard-fraud
```

## Tear down

```bash
docker compose down          # stops everything, keeps the postgres_data volume
docker compose down -v       # ALSO deletes all data -- only do this deliberately
```

## Rebuilding after a code change

- Changes under `shared/`, `airflow/dags/`, or `projects/*/pipeline.py` and `sql/`: **no rebuild
  needed** — these are bind-mounted into the Airflow containers, picked up live (DAG files within
  ~30s by the dag-processor's scan interval; `pipeline.py`/`sql/` changes take effect on the next
  task run, since each task loads the module fresh via `shared/dag_utils.py`).
- Changes under `projects/*/dashboard/app.py` or `shared/`: dashboard containers bake `shared/` and
  `projects/` into the image (see `docker/dashboard.Dockerfile`), so `docker compose up -d --build
  dashboard-<name>` is required to see the change.
- Changes to `airflow/requirements.txt` or `airflow/Dockerfile`: `docker compose build airflow-init`
  (all four Airflow services share one image via the `x-airflow-common` anchor) then restart.

## Known operational notes

- The very first `docker compose up` for `postgres` runs `database/init/*.sh` **once**, against a
  fresh volume — changes to those scripts after that have no effect until the volume is recreated
  (`docker compose down -v` then back up), since Postgres only runs `docker-entrypoint-initdb.d`
  on an empty data directory.
- Every DAG has a past `start_date`, so unpausing it immediately schedules a `scheduled__...` run
  in addition to anything you `dags trigger` manually — see the gotcha in `docs/airflow_guide.md`.
- Healthcheck timeouts for the scheduler/dag-processor are set to 30s (not Airflow's more common
  10s default) because `airflow jobs check`'s own cold-start cost showed up as a flaky `unhealthy`
  status under concurrent CPU load from other Docker projects on this machine — functionally
  harmless (confirmed via a full successful DAG run while "unhealthy"), but the longer timeout
  avoids the noise.
