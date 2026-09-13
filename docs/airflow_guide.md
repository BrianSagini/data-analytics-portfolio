# Airflow Guide

Airflow 3.3.1, LocalExecutor, FabAuthManager. UI at http://localhost:8081.

## DAGs

| DAG id | Project | Schedule | Key tasks |
|---|---|---|---|
| `climate_risk_pipeline` | 1 | `@daily` | source check, schema, load locations, extract (Open-Meteo), validate+load, SQL risk scoring, SQL financial impact, data-quality check |
| `dark_store_pipeline` | 2 | `@daily` | source check, schema, load stores, extract+clean (UCI download), validate, build+load products/orders/order_items, simulate+load inventory, SQL analytics, data-quality check |
| `hiring_bias_pipeline` | 3 | `@daily` | config check, schema, generate synthetic funnel, validate+load, SQL fairness metrics, train audit model, data-quality check |
| `fraud_pattern_pipeline` | 4 | `@daily` | schema, generate synthetic transactions, validate+load, graph analytics, anomaly detection, model evaluation, explainable alerts, SQL trends, data-quality check |

Every DAG:

- reads/writes only its own project's Postgres schema (`climate_risk`, `dark_store`,
  `hiring_bias`, `fraud_pattern`) inside the shared `analytics` database
- has a final `data_quality_check` task that fails the run on a real problem (null scores,
  orphaned foreign keys, non-monotonic funnels, a model no better than random) rather than a
  cosmetic green checkmark
- uses `ON CONFLICT DO UPDATE`/`DO NOTHING` upserts (`shared/database/connection.py`) keyed on
  natural keys, so re-running a DAG for the same logical date replaces that data instead of
  duplicating it
- passes data between tasks via parquet files in the container's temp dir (not raw dataframes
  through XCom, which has a size limit) and only small scalars/dicts through XCom itself

## Common commands

```bash
# import-time errors across all DAGs
docker compose exec airflow-scheduler airflow dags list-import-errors

# list DAGs and their paused state
docker compose exec airflow-scheduler airflow dags list

# unpause + trigger
docker compose exec airflow-scheduler airflow dags unpause <dag_id>
docker compose exec airflow-scheduler airflow dags trigger <dag_id>

# check a run's task states (dag_id is positional, not a flag)
docker compose exec airflow-scheduler airflow dags list-runs <dag_id>
docker compose exec airflow-scheduler airflow tasks states-for-dag-run <dag_id> <run_id>

# re-run a specific logical date's tasks after a fix
docker compose exec airflow-scheduler airflow tasks clear <dag_id> -y -s <YYYY-MM-DD> -e <YYYY-MM-DD>

# run one task in isolation for debugging (writes real DB rows, unlike a dry run)
docker compose exec airflow-scheduler airflow tasks test <dag_id> <task_id> <YYYY-MM-DD>
```

## Gotcha: a scheduled run queues behind your manual trigger

Every DAG has a `start_date` in the past, so unpausing one immediately schedules a `scheduled__...`
run for it -- if you then `dags trigger` a `manual__...` run too, `max_active_runs=1` queues the
manual one behind the scheduled one. Check `airflow dags list-runs <dag_id>` for the actual running
run's `run_id` rather than assuming it's the one you just triggered.

## Credentials

Airflow admin user is created idempotently by the `airflow-init` one-shot container (`airflow users
list | grep -q ... || airflow users create ...`) -- safe to re-run without creating a duplicate.
No DAG hardcodes a secret; all come from `.env` via `env_file:` in `docker-compose.yml`.
