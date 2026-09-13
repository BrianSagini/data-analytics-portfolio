# Power BI Guide

## Status (verified 2026-09-13, honestly)

- **Power BI Desktop is installed** on this machine (Microsoft Store package
  `Microsoft.MicrosoftPowerBIDesktop`, version 2.157.1354.0) — confirmed via
  `Get-AppxPackage`.
- **A live GUI build/test of the reports was not performed.** Building a real Power BI
  report (clicking through Get Data, dragging fields, writing DAX in the Desktop UI) requires
  interactive use of a graphical application; this session has no UI-automation tool installed
  (no Playwright-for-desktop, no `pywinauto`) to drive it, and Windows Store app packages are
  ACL-locked against the kind of filesystem inspection that could substitute for opening it.
  Hand-authoring the underlying `.pbip`/TMDL project files blind, without the ability to actually
  open and iterate on them in Power BI Desktop, would risk producing something that *claims* to
  work but silently doesn't — which is exactly what this project's instructions prohibit ("never
  fabricate Power BI publication," "do not claim a report is openable until it has been tested").
  So instead of guessing at a binary/project format that can't be verified here, this guide gives
  the exact, correct, ready-to-follow steps for a person (or a future session with interactive
  desktop access) to build all four reports in ~15-20 minutes each.
- **Power BI Service publication was not attempted** — it requires a Power BI account,
  workspace, and (for a local Postgres source) either an On-premises Data Gateway or Power BI
  running against a publicly reachable instance, none of which exist here. See
  [Service publication](#power-bi-service-publication-blocked) below.
- What **is** done and real: four Postgres views per project (13 total, `*.powerbi_*`), created
  by each pipeline's `create_powerbi_views` Airflow task, granted to the read-only
  `analytics_ro` role — the exact same views this guide's Get Data steps point at. These were
  verified with real `SELECT` queries against the read-only role (see
  `docs/final_verification_report.md`).

## Data connectivity

Every report connects to the same source:

- Connector: **Get Data → Database → PostgreSQL database**
- Server: `localhost:5433` (from a machine with the Docker stack running — see
  `docker-compose.yml`; the container-internal port 5432 is irrelevant to Power BI Desktop,
  which runs on the host)
- Database: `analytics`
- Username: `analytics_ro` / password: value of `ANALYTICS_RO_PASSWORD` in `.env` (never commit
  this — Power BI stores it in its local credential manager, not inside the `.pbix`/`.pbip` file)
- **Mode: Import**, not DirectQuery. Reasoning: these views aggregate at most tens of thousands
  of rows (the largest, `dark_store.powerbi_sales_summary`, is one row per store per day — a
  few thousand rows), so Import gives a fully interactive report with no live round-trip to
  Postgres per click, and works even if the local Docker stack isn't running at demo time (after
  the first refresh). DirectQuery would be the right call for the underlying multi-hundred-
  thousand-row fact tables, but this guide's reports load from the pre-aggregated `powerbi_*`
  views specifically so Import stays practical.
- Power BI Desktop bundles its own PostgreSQL driver (Npgsql) as of recent versions — no
  separate driver install should be required, but if Get Data prompts for one, install the
  official Npgsql ODBC/`.NET` driver from postgresql.org, not a third-party mirror.

## Report 1 — Climate Risk & Business Impact

Tables to import (Get Data → PostgreSQL → pick these 3):
- `climate_risk.powerbi_summary` (1 row/location — the model's "dimension+latest facts" table)
- `climate_risk.powerbi_trends` (1 row/location/month)
- `climate_risk.powerbi_financial_impact` (1 row/location/year/scenario)

Relationships: `powerbi_summary[location_id]` (1) → `powerbi_trends[location_id]` (*),
`powerbi_summary[location_id]` (1) → `powerbi_financial_impact[location_id]` (*).

Measures (add to `powerbi_summary` unless noted):
```
Total Business Exposure = SUM(powerbi_summary[asset_value_usd])
Avg Risk Score = AVERAGE(powerbi_summary[latest_risk_score])
Total Estimated Impact = SUM(powerbi_financial_impact[estimated_impact_usd])
Highest Risk Location = TOPN(1, powerbi_summary, powerbi_summary[latest_risk_score], DESC)
```

Pages:
1. **Executive Overview** — cards for Total Business Exposure / Avg Risk Score / Total Estimated
   Impact; a bar chart of `latest_risk_score` by `name`.
2. **Climate Trends** — line chart of `avg_temp_max_c`/`avg_temp_min_c` over `month` from
   `powerbi_trends`, filterable by `location_id`.
3. **Geographic Risk** — a Map/Azure Map visual using `lat`/`lon` from `powerbi_summary`, sized
   and colored by `latest_risk_score`.
4. **Business Impact** — bar chart of `estimated_impact_usd` by `name`, sliced by `scenario`;
   a text box noting the impact model is illustrative (same disclosure as the Streamlit dashboard
   and `docs/methodology_climate_risk.md`).

## Report 2 — Dark Store Intelligence

Tables: `dark_store.powerbi_sales_summary`, `dark_store.powerbi_inventory_summary`,
`dark_store.powerbi_store_performance`.

Measures:
```
Total Revenue = SUM(powerbi_sales_summary[revenue])
Total Orders = SUM(powerbi_sales_summary[orders_count])
Avg Order Value = DIVIDE([Total Revenue], [Total Orders])
Total Profit (Est.) = SUM(powerbi_store_performance[profit_estimate])
```

Pages: Executive Overview (cards + revenue-by-store bar) · Sales Analysis (revenue over time by
store) · Inventory Analysis (from `powerbi_inventory_summary`: days-of-supply, stockout days,
turnover ratio) · Store Performance (profit/ROI by store, from `powerbi_store_performance`).
Every visual pulling from a `*_summary` view should carry a note that store assignment,
inventory, and cost figures are synthetic (same disclosure as `docs/methodology_dark_store.md`).

## Report 3 — AI Hiring Bias Detector

Tables: `hiring_bias.powerbi_funnel_summary`, `hiring_bias.powerbi_fairness_summary`,
`hiring_bias.powerbi_group_comparison`.

Measures:
```
Total Applications = SUM(powerbi_funnel_summary[total_applications])
Overall Hire Rate = DIVIDE(SUM(powerbi_funnel_summary[reached_hire]), [Total Applications])
```
(Selection rate and adverse-impact ratio are already computed per-row in SQL by
`002_fairness_metrics.sql` — expose them as columns, not re-derived DAX, so Power BI can never
disagree with the SQL model or the Streamlit dashboard.)

Pages: Executive Overview (funnel counts by stage) · Recruitment Funnel (stage-to-stage
conversion, from `powerbi_funnel_summary`) · Fairness Analysis (selection rate and
`adverse_impact_ratio` by group, with a reference line at 0.8 for the four-fifths rule, from
`powerbi_group_comparison`) · Methodology (text page: synthetic-data disclosure, fairness
definitions, limitations — copy from `docs/methodology_hiring_bias.md`).

**This report must never rank or recommend candidates** — it only ever aggregates at the
group/stage level, matching the constraint already enforced in the Streamlit dashboard and the
underlying SQL (no per-candidate scoring view exists).

## Report 4 — Fraud Pattern Evolution Tracker

Tables: `fraud_pattern.powerbi_risk_summary`, `fraud_pattern.powerbi_trends`,
`fraud_pattern.powerbi_network_summary`.

Measures:
```
Total Transactions = SUM(powerbi_risk_summary[total_transactions])
True Fraud Rate = AVERAGE(powerbi_risk_summary[true_fraud_rate])
```
(Precision/recall/ROC-AUC are already single-row model outputs in `powerbi_risk_summary` —
expose as columns/cards, not recomputed.)

Pages: Executive Overview (cards: total transactions, flagged, true fraud rate, ROC-AUC) · Fraud
Trends (from `powerbi_trends`: `fraud_rate`/`fraud_amount` over `month`) · Detection Performance
(precision/recall/F1/ROC-AUC cards, with a text note on why precision is low at this threshold —
same explanation as `docs/methodology_fraud_pattern.md`'s "Observed results" section) ·
Suspicious Activity (from `powerbi_network_summary`: table of `is_ring_candidate` accounts by
`component_size`).

State clearly on every page that all transaction/account data is synthetic.

## Power BI Service publication: BLOCKED

Publishing any of the four reports to Power BI Service requires, at minimum: (1) a Power BI
account with a workspace the publisher has write access to, and (2) for a report backed by a
local (non-cloud) Postgres instance, either an **On-premises Data Gateway** installed and
configured on a machine that can reach `localhost:5433`, or switching the reports to Import mode
and only ever manually refreshing from Desktop (no scheduled refresh). Neither a Power BI
account/workspace nor a gateway exists in this environment, and provisioning either is an
account-level decision outside what this session can infer or configure safely. If you want this
step done: sign in to Power BI Desktop (top-right "Sign in"), confirm a workspace under
**Workspaces**, then **File → Publish → Publish to Power BI**; for a gateway, see
https://learn.microsoft.com/power-bi/connect-data/service-gateway-onprem.
