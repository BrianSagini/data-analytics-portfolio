# Database Schema

One Postgres 16 instance (`analytics-portfolio-postgres`, host port 5433), two databases:

- `airflow` — Airflow's own metadata, owned by the `airflow` role. Nothing else reads/writes it.
- `analytics` — this portfolio's data, one schema per project, owned by the `analytics` role.
  A read-only role `analytics_ro` (used by every Streamlit dashboard) has `SELECT` on all four
  schemas via `ALTER DEFAULT PRIVILEGES`, set up once in `database/init/01_init.sh`.

## `climate_risk` (Project 1)

| Table | Grain | Notes |
|---|---|---|
| `locations` | 1 row/location | real lat/lon; synthetic industry/revenue/asset_value (`is_synthetic_business_data`) |
| `daily_climate` | 1 row/location/day | real, from Open-Meteo |
| `risk_scores` | 1 row/location/year | SQL-computed heuristic (see `docs/methodology_climate_risk.md`) |
| `scenario_financial_impact` | 1 row/location/year/scenario | SQL-computed, 3 scenarios |

## `dark_store` (Project 2)

| Table | Grain | Notes |
|---|---|---|
| `stores` | 1 row/store (6) | fully synthetic (`is_synthetic`) |
| `products` | 1 row/`stock_code` | real (from UCI dataset) |
| `orders` | 1 row/invoice | real order header; `store_id` assignment synthetic |
| `order_items` | 1 row/invoice/stock_code | real line items |
| `inventory_snapshots` | 1 row/store/product/day | fully synthetic simulation (`is_synthetic`) |
| `store_daily_metrics`, `inventory_analysis`, `store_profitability`, `cross_store_correlation` | SQL-computed analytics | see `docs/methodology_dark_store.md` |

## `hiring_bias` (Project 3)

| Table | Grain | Notes |
|---|---|---|
| `candidates` | 1 row/synthetic candidate (20k) | fully synthetic (`is_synthetic`), includes funnel-stage booleans |
| `fairness_metrics` | 1 row/attribute/group/stage | SQL-computed selection rates + 4/5ths adverse impact ratio |
| `audit_model_coefficients` | 1 row/model feature | interpretability only, never used to score candidates |

## `fraud_pattern` (Project 4)

| Table | Grain | Notes |
|---|---|---|
| `accounts` | 1 row/synthetic account (5k) | fully synthetic; `is_fraud_ring_member`/`ring_id` are ground truth |
| `transactions` | 1 row/synthetic transaction (~150k+) | fully synthetic; `is_fraud` is ground truth |
| `graph_metrics` | 1 row/account | from `networkx` connected-components over shared device/IP |
| `anomaly_scores` | 1 row/transaction/model | `IsolationForest` output, never sees the fraud label |
| `model_evaluation` | 1 row/model | precision/recall/F1/ROC-AUC against ground truth |
| `fraud_trends` | 1 row/month | SQL-computed |
| `alerts` | 1 row/transaction/reason | rule-based, explainable |

## Conventions

- Every fact table has a natural-key primary key (never a surrogate autoincrement id) so
  `ON CONFLICT DO UPDATE`/`DO NOTHING` upserts (`shared/database/connection.py`) make reruns
  idempotent by construction.
- Every synthetic table/column is named or flagged `is_synthetic[...]` — see each project's
  `docs/methodology_*.md` for exactly what that covers.
- SQL analytical models live as plain `.sql` files under each project's `sql/` directory, run by
  a dedicated Airflow task via `shared.database.run_sql_file` — never embedded as Python strings.
