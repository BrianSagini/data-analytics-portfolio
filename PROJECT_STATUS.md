# Project Status

Last updated: 2026-09-13 (Power BI + browser-testing + Git session). **All four projects complete
and verified end-to-end; see `docs/final_verification_report.md` for the full PASS/FAIL/BLOCKED
breakdown against every item in this project's definition of done.**

## 2026-09-13 session additions

- Added 13 `*.powerbi_*` read-only Postgres views (one set per project) and a new
  `create_powerbi_views` Airflow task in each DAG. `docs/powerbi_guide.md` has exact Get
  Data/measures/page-layout instructions for all 4 reports — Power BI Desktop is confirmed
  installed, but building/testing the actual `.pbip` report interactively was not done (no
  desktop-automation tool in this session); documented honestly as BLOCKED rather than faked.
- Real browser testing of all 4 dashboards with Playwright/Chromium (`docs/browser_testing.md`),
  replacing the previous "container started without error" level of verification. Found and
  fixed one real gap (fraud dashboard had no filter widget at all) and one test-script timing bug
  (dark store's charts were never actually missing, just not yet drawn at a too-short wait).
- KPI reconciliation: SQL vs. Power BI view vs. Streamlit dashboard, spot-checked one KPI per
  project — all matched exactly (they're the same underlying tables/views, so this is a
  by-construction guarantee re-verified, not a coincidence).
- `git init` + first commit (84+ files, `.env` and the raw UCI spreadsheet correctly excluded).
  No GitHub remote configured (needs user-provided auth/repo).
- **Docker Desktop crashed mid-session** (`docker ps` returned `500 Internal Server Error`,
  confirmed zero `docker`-named processes running). Restarted it, waited for the engine, and
  restarted this project's 4 dashboard containers (Postgres/Airflow auto-restarted on their own).
  No data lost. This crash also caused that day's automatic `@daily` DAG runs to fail (confirmed
  via `task_instance` — first task's network call failed right as the engine was unstable, not a
  code bug); fixed by re-triggering all four manually once the stack was stable again.

## Environment & infrastructure

- New isolated repo at `H:\Claude\data-analytics-portfolio`, separate from the pre-existing,
  unrelated `ai-video-factory` and `atlas-ai-trading` projects on this machine (see
  `docs/environment_audit.md` for the full audit and reuse rationale — no duplicate installs,
  no reused/overwritten databases, ports chosen to avoid the other two projects' 5432/5434/6379/8080).
- Docker stack, all running: Postgres 16 (host 5433, DBs `airflow` + `analytics`), Airflow 3.3.1
  (host 8081, LocalExecutor, FabAuthManager), 4 Streamlit dashboards (host 8501-8504).
- `docker compose ps`: postgres healthy, apiserver healthy, scheduler/dag-processor show
  "unhealthy" from healthcheck-timeout flakiness under this machine's concurrent multi-project CPU
  load — confirmed harmless (all 4 DAGs ran to completion while this showed), see `docs/deployment.md`.

## Project 1 — Climate Risk & Business Impact Analyzer: **DONE**

Real Open-Meteo climate history (10 cities, ~3yr) + synthetic business exposure. `climate_risk_pipeline`
DAG: 8/8 tasks succeeded. Dashboard live at :8501, no errors. Bugs found & fixed live: missing
`run_sql_file` export, comment-embedded semicolon breaking naive SQL-file splitting, Postgres 15+
`public` schema permissions, `ROUND(double precision,...)` needing a `numeric` cast.

## Project 2 — Dark Store Intelligence: **DONE**

Real UCI "Online Retail II" transactions (~541k rows, 1 sheet) + synthetic 6-store network,
inventory simulation, cost assumptions. `dark_store_pipeline` DAG: 12/12 tasks succeeded (full run
~36 min, dominated by openpyxl parsing the real 45MB spreadsheet). Dashboard live at :8502.
Sample results: revenue ranges $280k (FAR/DUB) to $3.3M (MAN) across stores; cross-store weekly
revenue correlation 0.39-0.72 (explicitly documented as a proxy, not real cannibalization —
synthetic store assignment doesn't create overlapping catchment areas).

## Project 3 — AI Hiring Bias Detector: **DONE**

100% synthetic, 20k candidates, documented/adjustable bias injection. `hiring_bias_pipeline` DAG:
7/7 tasks succeeded. Dashboard live at :8503. Sample results: gender adverse-impact ratios
0.90-1.00 across funnel stages (injected bias visible but diluted through qualification-driven
progression, as designed). Audit model is interpretability-only, never used to score candidates.

## Project 4 — Fraud Pattern Evolution Tracker: **DONE**

100% synthetic, 5k accounts / ~150k transactions, 15 injected fraud rings + organic fraud.
`fraud_pattern_pipeline` DAG: 9/9 tasks succeeded. Dashboard live at :8504. Real (checkable)
results: **ROC-AUC 0.93, recall 0.78, precision 0.12** against synthetic ground truth (1,115 true
fraud txns) — precision is low because `contamination=0.05` over-flags relative to the true 0.75%
fraud rate, documented as a threshold-tuning limitation, not a bug. 14,966 explainable alerts
generated (two independent signals: anomaly score + shared-device/IP graph cluster).

## No credential blockers

No project needed an API key. All four data sources (2 real, 2 synthetic-by-design) were verified
live, not assumed.

## Remaining possible follow-ups (not blockers)

- Dashboards were smoke-tested for startup, DB connectivity, and absence of script errors in
  container logs; interactive UI testing (clicking filters in a real browser) was not performed —
  see final report for exactly what "tested" means here.
- Fraud model's flag threshold (`contamination=0.05`) could be recalibrated closer to the true
  ~0.75% prevalence for higher precision — documented as a natural next tuning step, not required
  for the demo's purpose (methodology, not a production detector).
