# Final Verification Report

Generated: 2026-09-13. Status values used below: `PASS`, `FAIL`, `BLOCKED`, `NOT TESTED`,
`NOT APPLICABLE`.

## 1. Environment audit summary

Full detail in `docs/environment_audit.md`. Windows 11 Pro, Docker Desktop 29.6.2 (Docker
Compose v5.3.1), Python 3.14.2 (global) with a project-local `.venv`, Git 2.55.0. Power BI
Desktop confirmed installed (`Microsoft.MicrosoftPowerBIDesktop` 2.157.1354.0, Microsoft Store
package). No global Node/npx. **PASS**

## 2. Existing applications/services detected

Two other, unrelated Docker Compose projects already running on this machine before this
portfolio existed: `ai-video-factory` (Postgres/pgvector on :5432, Redis on :6379) and
`atlas-ai-trading` (its own isolated Airflow 3.3.1 on :8080, TimescaleDB on :5434). Neither was
modified, stopped, or reset. **PASS**

## 3. Infrastructure reused

Base Docker images already pulled locally and reused without re-downloading:
`apache/airflow:3.3.1-python3.13`, `postgres:16`. No native Airflow/Postgres install exists on
this machine outside Docker. **PASS**

## 4. Infrastructure installed

One new, isolated Docker Compose stack for this repo only: Postgres 16 (host :5433, two logical
databases — `airflow` metadata + `analytics` app data), Airflow 3.3.1 (LocalExecutor, FAB auth,
host :8081), four Streamlit dashboard containers (:8501-8504). Playwright + Chromium installed
into the repo's local `.venv` for browser testing (not global). **PASS**

## 5. Infrastructure repaired

- Fixed `database/init/01_init.sh`: Postgres 15+ no longer grants `CREATE` on `public` to new
  roles by default, which broke `airflow db migrate` on first boot — added an explicit `GRANT ALL
  ON SCHEMA public`.
- Fixed a version conflict in `airflow/requirements.txt`: exact pins on `pandas`/`sqlalchemy`/
  `requests`/`scikit-learn` downgraded packages Airflow's own providers required — switched to
  floor constraints (`>=`) so nothing already satisfied by the base image gets downgraded.
- Recovered from a **Docker Desktop engine crash** that occurred mid-session (confirmed via
  `docker ps` returning `500 Internal Server Error` and zero `docker`-named processes running) —
  restarted Docker Desktop, waited for the engine, and restarted this project's 4 dashboard
  containers, which had exited and not auto-restarted (Postgres and Airflow's containers did
  auto-restart via their `restart: unless-stopped` policy and came back healthy on their own).
  Verified afterward that no data was lost (Postgres volume persisted; all row counts matched
  pre-crash values). `ai-video-factory-postgres-1`/`ai-video-factory-redis-1` also exited from the
  same crash and were deliberately left alone per this project's instruction not to touch that
  project. **PASS** (repaired within scope; out-of-scope containers correctly left for the user)
- This Docker crash also caused that day's **automatic `@daily`-scheduled runs** of all four DAGs
  to fail (their first task's network/DB call executed right as the engine was unstable). Root
  cause confirmed via `task_instance` query, not assumed. Fixed by re-triggering all four
  manually once the stack was stable; see §7.

## 6. Duplicate-installation checks

No second Airflow install, no second Airflow admin user, no second Postgres server, no
unnecessary Redis/Celery (LocalExecutor needs none). Host ports (5433, 8081, 8501-8504) chosen
specifically to avoid the four already in use by the other two projects. **PASS**

## 7. Airflow DAG execution results

All four DAGs' `.py` files import cleanly (`airflow dags list-import-errors` → no data found)
after adding a `create_powerbi_views` task to each. Fresh, real, timestamped runs triggered after
the Docker Desktop recovery (not reused from before the crash):

| DAG | Result | Notes |
|---|---|---|
| `climate_risk_pipeline` | **PASS** — success, 05:50:33→05:57:06 (6m33s) | 8→9 tasks (added `create_powerbi_views`) |
| `hiring_bias_pipeline` | **PASS** — success, 05:49:49→06:00:58 (11m9s) | 7→8 tasks |
| `fraud_pattern_pipeline` | **PASS** — success, 05:50:48→06:08:46 (17m58s) | 9→10 tasks |
| `dark_store_pipeline` | **PASS** — success, 05:49:27→06:19:09 (29m42s) | 12→13 tasks |

All four confirmed via a direct query against Airflow's own metadata database
(`dag_run`/`task_instance` tables), not the `airflow` CLI's (broken, wrong-flag) `list-runs`
output — every task in every run reached `success`, including the new `create_powerbi_views`
task in each DAG.

## 8. Database validation results

Schemas, tables, and 13 Power BI views (`*.powerbi_*`, one set per project) exist in the
`analytics` database, one schema per project, with natural-key primary keys throughout (no
surrogate autoincrement ids), so reruns are idempotent by construction (`ON CONFLICT DO
UPDATE`/`DO NOTHING`). Read-only role `analytics_ro` confirmed able to `SELECT` from all new
views. **PASS**

## 9. Streamlit browser-testing results

Full detail in `docs/browser_testing.md`. Real headless-Chromium test (Playwright), not just
"container started": all four dashboards load, show a correct title and real data-backed
content, render charts (6-12 per page) and metric cards, respond to a real filter interaction
(tag removal or radio switch) without crashing, produce zero console/JS errors, and render
correctly at a 480px-wide viewport. Screenshots in `scripts/browser_test_screenshots/`. **PASS**

Two real issues found and fixed during this pass (not test-script false negatives, confirmed by
reading the actual dashboard code): the fraud dashboard had zero interactive filter widgets
(added one); a test-script timing bug initially under-counted the dark store dashboard's charts
(the dashboard itself was never broken — confirmed by a longer-wait diagnostic).

## 10. Power BI report creation results

Thirteen Postgres views created and verified (one set per project, `climate_risk.powerbi_*`,
`dark_store.powerbi_*`, `hiring_bias.powerbi_*`, `fraud_pattern.powerbi_*`), each created by a new
`create_powerbi_views` Airflow task (not just run manually once). **A `.pbip`/`.pbix` report file
was not created.** Full reasoning in `docs/powerbi_guide.md`: hand-authoring the TMDL/PBIR project
format blind, with no way to open and iteratively verify it in Power BI Desktop from this
non-interactive session, risks producing a file that claims to work but doesn't — which this
project's own instructions explicitly forbid. Instead, `docs/powerbi_guide.md` gives the exact,
correct connection settings, tables, DAX measures, and page layouts for all four reports, ready to
build in ~15-20 minutes each once someone has interactive access to Power BI Desktop. **BLOCKED**
(no interactive desktop-automation capability in this session) — with real, usable preparatory
work done, not a placeholder.

## 11. Power BI report validation results

**NOT TESTED** — depends on §10. Power BI Desktop itself is confirmed installed (§1) but no
report file exists yet to validate.

## 12. Power BI Service publication results

**BLOCKED** — no Power BI account/workspace/gateway is configured in this environment, and none
of those can be provisioned from this session. See `docs/powerbi_guide.md`'s "Power BI Service
publication: BLOCKED" section for exactly what a person would need to do.

## 13. KPI reconciliation results

Executed the underlying SQL directly and compared against (a) the value a running Streamlit
dashboard displays and (b) the corresponding Power BI view, for one KPI per project:

| Project | KPI | SQL source | Power BI view | Streamlit dashboard | Match |
|---|---|---|---|---|---|
| Dark Store | Total revenue / orders | `store_daily_metrics`: $10,667,354.24 / 19,960 | `powerbi_sales_summary`: same | Dashboard card: $10,667,354 / 19,960 | ✅ exact |
| Fraud | precision/recall/ROC-AUC | `model_evaluation`: 0.1161/0.7794/0.9268 | `powerbi_risk_summary`: same | Dashboard cards: 0.12/0.78/0.93 (rounded for display) | ✅ exact |
| Climate | Top-3 moderate-scenario impact by location | `scenario_financial_impact`: HOU $17.0M, NYC $7.58M, PHX $6.0M | `powerbi_summary`: same | Dashboard chart: same ranking/values | ✅ exact |
| Hiring | Gender adverse-impact ratio @ hire stage | `fairness_metrics`: Man 0.895, Non-binary 1.0, Woman 0.984 | `powerbi_group_comparison`: same + `fails_four_fifths_rule` derived flag | Dashboard table: same | ✅ exact |

No unexplained discrepancy found. The Power BI views are pure passthrough/join queries over the
same tables the dashboards read (no logic re-implemented), so this match is by construction, not
coincidence — verified anyway rather than assumed. **PASS**

## 14. Tests executed and actual results

- `shared/tests/test_validation.py` (5 unit tests, pure-Python validation logic): **PASS**, 5/5,
  run via `pytest` in the repo's local `.venv`.
- Real Airflow DAG runs (not `airflow dags test` dry-runs): see §7/§7a.
- Real browser tests: see §9.
- Real KPI reconciliation: see §13.

## 15. Errors found and fixes applied

See §5 for infrastructure-level fixes and §9 for dashboard-level fixes. One real business-logic
bug found during this pass's freshness check: `fraud_pattern.model_evaluation.computed_at` stayed
frozen at its very first INSERT forever, because `evaluate_model_and_load()` never included
`computed_at` in the dict passed to `upsert_dataframe` — `ON CONFLICT DO UPDATE` only refreshes
columns present in the upserted data, so every rerun silently left the timestamp claiming "first
ever run" instead of "most recent run." Found by comparing `model_evaluation`'s `computed_at`
(2026-09-12) against the DAG run that had just completed successfully (2026-09-13) — a real
discrepancy, not a false alarm. Fixed by explicitly setting `computed_at =
datetime.now(timezone.utc)` in the metrics dict; verified the fix directly (re-ran the function,
confirmed the column advanced to the current timestamp). Audited every other project for the same
pattern (any Python-side `upsert_dataframe` call writing to a table with a `computed_at` column
whose value isn't in the dict) — no other instance found; every other `computed_at` is set by a
SQL file's `INSERT ... ON CONFLICT DO UPDATE SET computed_at = EXCLUDED.computed_at`, which
already refreshes correctly.

## 16. Files created or modified (this session)

New: `docs/powerbi_guide.md`, `docs/browser_testing.md`, `docs/final_verification_report.md`,
4× `sql/0NN_powerbi_views.sql` (one per project), `scripts/browser_test_dashboards.py` +
screenshots + results JSON, `.git/` (new repository + initial commit).
Modified: all 4 `airflow/dags/*.py` (added `create_powerbi_views` task), `.gitignore` (Power BI
cache/credential exclusions, broadened `*.env`/`*.log`/`secrets/`/`credentials/`),
`projects/04_fraud_pattern_evolution/dashboard/app.py` (added a severity filter), `README.md`
(Power BI/browser-testing/git/troubleshooting sections), `PROJECT_STATUS.md`.

## 17. Git status

Repository initialized at `H:\Claude\data-analytics-portfolio`; one commit (`Initial commit:
4-project data analytics portfolio`) containing 84+ files. `.env` and the raw UCI spreadsheet are
correctly excluded (verified via `git ls-files` before committing — neither appears). **No GitHub
remote configured** — this needs a GitHub account/repo this session isn't authorized to create;
exact commands to do it are in `README.md`'s Git/GitHub section. **PASS** (local git) /
**BLOCKED** (GitHub push — needs user-provided remote/auth)

## 18. Remaining blockers

1. Power BI report files not built/tested interactively (§10-11) — needs a person with Power BI
   Desktop's GUI, or a future session with desktop-automation tooling.
2. Power BI Service publication (§12) — needs a Power BI account, workspace, and (for a local
   Postgres source) an On-premises Data Gateway.
3. GitHub push (§17) — needs a GitHub remote and credentials this session doesn't have.

None of these block local use of the four pipelines/dashboards, which are fully functional.

## 19. Exact commands to run the system

See `README.md`'s "Quick start" section — reproduced in full there, not duplicated here to avoid
the two drifting out of sync.

## 20. Final portfolio-readiness assessment

**Ready for local demonstration now**: all four Airflow pipelines run end-to-end against
real-or-honestly-labeled-synthetic data, all four dashboards are real-browser-tested and their
KPIs reconcile exactly against the database, and Power BI has real, verified read-only views
ready to connect to. **Not yet ready** for a Power BI Service demo or a public GitHub link without
the three blockers in §18 being resolved by someone with the missing account/tool access.
