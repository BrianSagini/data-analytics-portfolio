# Data Analytics Portfolio

Four analytics projects, one shared Airflow + Postgres stack, a genuinely different problem in
each: climate risk scoring, retail fulfillment economics, hiring-fairness auditing, and fraud
detection with graph analytics. Every pipeline ingests data (real where I could get it, honestly
labeled synthetic where I couldn't), validates and transforms it, loads it into Postgres, computes
its analytics in SQL, and serves both a Streamlit dashboard and a Power BI report from the same
underlying views.

| # | Project | Data | Dashboard |
|---|---|---|---|
| 1 | [Climate Risk & Business Impact](projects/01_climate_risk_business_impact/) | Real (Open-Meteo) + synthetic business exposure | [Live dashboard](https://climate-risk-business-impact.streamlit.app/) |
| 2 | [Dark Store Intelligence](projects/02_dark_store_intelligence/) | Real (UCI Online Retail II) + synthetic store/inventory | [Live dashboard](https://dark-store-intelligence.streamlit.app/) |
| 3 | [AI Hiring Bias Detector](projects/03_ai_hiring_bias_detector/) | 100% synthetic (documented bias injection) | [Live dashboard](https://ai-hiring-bias-detector.streamlit.app/) |
| 4 | [Fraud Pattern Evolution Tracker](projects/04_fraud_pattern_evolution/) | 100% synthetic (documented fraud-ring injection) | [Live dashboard](https://fraud-pattern-evolution.streamlit.app/) |

Each is also published as its own self-contained repo if you want to see one in isolation:
[climate-risk-business-impact-analyzer](https://github.com/BrianSagini/climate-risk-business-impact-analyzer),
[dark-store-intelligence-dashboard](https://github.com/BrianSagini/dark-store-intelligence-dashboard),
[ai-hiring-bias-detector](https://github.com/BrianSagini/ai-hiring-bias-detector),
[fraud-pattern-evolution-tracker](https://github.com/BrianSagini/fraud-pattern-evolution-tracker).
This repo is where I actually built and ran them together, sharing one Airflow instance.

See `docs/data_sources.md` for exactly what's real vs. synthetic in each project, and each
project's `docs/methodology_*.md` for formulas, assumptions, and limitations I want a reader to
know about, not just the results.

## Running it

```bash
cp .env.example .env
# Airflow 3's apiserver won't start without real secrets here -- generate them first:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # -> AIRFLOW_FERNET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"                                 # -> AIRFLOW_JWT_SECRET
# paste both into .env

docker compose up -d --build postgres airflow-init airflow-apiserver airflow-scheduler airflow-dag-processor
docker compose ps   # airflow-init should exit 0, everything else healthy/starting
```

Airflow's at http://localhost:8081. From there, or the CLI:

```bash
docker compose exec airflow-scheduler airflow dags unpause climate_risk_pipeline
docker compose exec airflow-scheduler airflow dags trigger climate_risk_pipeline
```

DAG ids: `climate_risk_pipeline`, `dark_store_pipeline`, `hiring_bias_pipeline`,
`fraud_pattern_pipeline`. Once a DAG's completed at least one run, bring up its dashboard:

```bash
docker compose up -d --build dashboard-climate     # :8501
docker compose up -d --build dashboard-darkstore    # :8502
docker compose up -d --build dashboard-hiring       # :8503
docker compose up -d --build dashboard-fraud        # :8504
```

`docker compose down` shuts everything down without touching the data.

## How it's laid out

```
airflow/dags/            one DAG per project
database/init/           first-boot Postgres bootstrap (roles, schemas)
shared/                  ingestion/validation/database helpers used by every DAG
projects/0N_*/           each project's pipeline.py, sql/, dashboard/app.py, data_raw/
powerbi/0N_*/            each project's .pbip report, mirrored from its standalone repo
docs/                    architecture notes, data sourcing, methodology, build log
```

I isolated this whole stack deliberately — its own Postgres, its own Airflow, ports chosen to
avoid clashing with anything else already running on the machine I built this on. The reasoning
(what else was already running, why I didn't reuse it, service/port/executor choices) is in
`docs/environment_audit.md` and `docs/architecture.md`.

## Power BI

Every project's Postgres schema exposes read-only `*.powerbi_*` views — the same underlying data
the Streamlit dashboards read, so the two can never disagree. On top of those, I hand-built a
complete Power BI report per project: real semantic models (tables, relationships, DAX measures
checked field-by-field against the SQL), a themed design (a tinted canvas per project's own
accent palette, dense grids instead of visuals floating in half-empty pages, semantic accent
colors — red for risk, green for revenue, amber for warnings), and I opened every page of every
report in Power BI Desktop myself and confirmed it renders with real data before calling any of it
done. Screenshots are in each project's `docs/evidence/`.

```
powerbi/01_climate_risk_business_impact/ClimateRisk.pbip           4 pages, 22 visuals
powerbi/02_dark_store_intelligence/DarkStoreIntelligence.pbip      4 pages, 23 visuals
powerbi/03_ai_hiring_bias_detector/HiringBiasDetector.pbip         4 pages, 20 visuals
powerbi/04_fraud_pattern_evolution/FraudPatternEvolution.pbip      2 pages, 16 visuals
```

Fraud's report is 2 pages instead of 4 — I originally split it the same way as the others, found
two of those pages duplicated a table and a card outright, and merged them rather than leave the
duplication in. Full design reasoning and page-by-page detail live in each project's own repo
(linked at the top) under `docs/powerbi_guide.md`; the story of how I actually got here across all
four — the real bugs, the wrong assumptions I had to correct — is in `docs/how_i_built_this.md`.

## Everything else I verified

Real Airflow runs, real headless-browser testing of all four dashboards, and a KPI reconciliation
that traces one number per project through SQL → Power BI view → live dashboard and checks they
agree exactly — plus the real bugs that surfaced along the way and how I fixed them. All of that
is in `docs/how_i_built_this.md` rather than kept as a separate pass/fail audit log.

## If something breaks

- **Airflow apiserver crashes with `api_auth/jwt_secret must be set!`**: `AIRFLOW_FERNET_KEY` /
  `AIRFLOW_JWT_SECRET` are empty in `.env` — generate real values (see Running it above).
- **`permission denied for schema public` during `airflow db migrate`**: only comes up if you
  changed `database/init/01_init.sh` and recreated the `postgres_data` volume — Postgres 15+
  stopped granting `CREATE` on `public` by default; the init script already handles it.
- **A dashboard shows "No data yet"**: its DAG hasn't completed a run — trigger it and wait;
  Dark Store in particular takes 30–40 minutes because it parses a real ~45MB spreadsheet.

## Git

This repo stays local-only by design — no GitHub remote — since each project is published
independently (see the links at the top). If you want to push it anyway:

```bash
gh repo create <name> --private --source=. --remote=origin
git push -u origin master
```
