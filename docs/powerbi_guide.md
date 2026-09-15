# Power BI Guide

## Status (last verified 2026-09-15 — read this before anything else)

- **Power BI Desktop is installed** on this machine (Microsoft Store package
  `Microsoft.MicrosoftPowerBIDesktop`, version **2.157.1354.0**) — confirmed via
  `Get-AppxPackage`, and it launches successfully (confirmed via `Get-Process PBIDesktop`).
- **No `.pbix`/`.pbip` report file has been created, opened, or validated.** Two independent
  attempts to establish a safe path to real artifacts were made across this project's sessions,
  and both were correctly ruled out rather than worked around:
  1. Hand-authoring the `.pbip`/TMDL project format blind, with no way to open and iteratively
     verify it in Power BI Desktop — risks producing a file that *claims* to work but silently
     doesn't, which this project's instructions explicitly prohibit.
  2. Launching Power BI Desktop and validating it via a full-screen screenshot — attempted once,
     and immediately stopped: this machine is a live, actively-used desktop, not an isolated
     environment, and the resulting screenshot captured unrelated personal content (browser tabs,
     job-search activity) that had nothing to do with Power BI. That screenshot was deleted
     immediately and never left the local filesystem (confirmed never staged in git). No further
     screenshot-based validation was attempted after that, by the project owner's own explicit
     decision — see `docs/final_release_audit_report.md`'s Power BI section for the full account.
  Building the real reports therefore requires a person with interactive access to this machine's
  Power BI Desktop (or their own copy, pointed at the same Postgres source). This guide gives
  everything needed to do that in ~15-20 minutes per report: exact connection settings, tables,
  relationships, DAX measures, page-by-page layout, and the color/typography system below.
- **Power BI Service publication was not attempted** — see
  [Service publication](#power-bi-service-publication-blocked) below.
- What **is** done, real, and verified: 13 read-only `*.powerbi_*` Postgres views (one set per
  project — listed under each report below), created by each pipeline's `create_powerbi_views`
  Airflow task (not a one-off manual script), granted to the read-only `analytics_ro` role, and
  spot-checked against the underlying SQL tables with an exact match (`docs/final_verification_report.md`
  §13). The DAX measures below were written against, and every one manually reconciled to, those
  same already-verified SQL values — but "reconciled on paper" is not the same claim as "returns
  this value when actually evaluated by Power BI's engine," which requires opening the report.

## Design system (deliberate, not random)

One shared base + one accent set per project, applied consistently across all four reports.

**Typography**: Segoe UI (Power BI Desktop's default — already accessible, no reason to
override). Report title 24pt semibold · page/section headers 14pt semibold · KPI card values
28-32pt bold · body/axis labels 10-11pt regular. Every page carries the same header band (report
name, left-aligned; page name; a small "synthetic data" or "real + synthetic" badge where
relevant) and the same footer (data source + last-refresh placeholder + a one-line methodology
pointer), so the four reports read as one consistent portfolio, not four unrelated files.

**Shared base**: background `#F7F8FA` (near-white, not stark white — reduces glare on KPI cards),
primary text `#1A1A2E`, gridlines/borders `#E2E5EA`, neutral/muted `#6B7280`.

| Project | Primary (headers/nav) | Secondary accent | Positive/good | Warning | Critical/high-risk |
|---|---|---|---|---|---|
| 1. Climate Risk | Navy `#1B3A5C` | Teal `#2E8B99` | Blue `#3B82C4` (env. measures, neutral-good) | Amber `#E8A33D` | Red `#C0392B` |
| 2. Dark Store | Navy `#1B2A4A` | Purple `#6C4AB6` | Green `#2E9E5B` (revenue/profit up) | Orange `#E67E22` (stock concern) | Red `#C0392B` (loss/stockout) |
| 3. Hiring Bias | Blue `#2C5F8A` | Teal `#2E8B99` | *(none — see note)* | Amber `#E8A33D` | Red `#C0392B` |
| 4. Fraud | Navy `#14213D` | Teal `#2E8B99` | Neutral gray `#94A3B8` (normal txns) | Amber `#E8A33D` (suspicious) | Red `#C0392B` (confirmed/high-risk) |

**Hiring Bias demographic-group colors** (deliberately *not* semantic — see the design brief's
own instruction not to stigmatize any group with color): assign group values a fixed, neutral
qualitative sequence — Blue `#2C5F8A`, Purple `#6C4AB6`, Teal `#2E8B99`, Slate `#64748B`, Steel
`#7C93B0` — in the *order they appear in the data*, never by category meaning. Amber/red are
reserved exclusively for the fairness-threshold indicator (adverse-impact ratio < 0.8), never for
a group itself.

**Chart types**: bar/column and line charts for nearly everything (categorical comparison and
trend are almost every visual here); a real map visual only for climate's lat/lon locations and
optionally fraud's `home_country`; plain tables for the funnel/network/detail pages. No pie
charts, no 3D, no gauges, no unjustified decorative visuals — the data here (rates, trends,
rankings) is well served by bars and lines, and nothing in these four datasets needs a gauge or
donut to read correctly.

## Data connectivity

Every report connects to the same source:

- Connector: **Get Data → Database → PostgreSQL database**
- Server: `localhost:5433` · Database: `analytics`
- Username: `analytics_ro` / password: value of `ANALYTICS_RO_PASSWORD` in `.env` (Power BI
  stores this in its own local credential manager, never inside the `.pbix`/`.pbip` file — nothing
  from `.env` should ever be pasted into a report's M query text)
- **Mode: Import**, not DirectQuery — these views aggregate at most tens of thousands of rows
  (the largest, `dark_store.powerbi_sales_summary`, is roughly one row per store per day), so
  Import gives a fully interactive report that still works if the local Docker stack isn't running
  at demo time (after the first refresh). Connect to the `powerbi_*` views specifically, not the
  raw multi-hundred-thousand-row fact tables — DirectQuery against those would be the right call
  for a production deployment, but isn't necessary here and would make Import's offline-demo
  benefit moot.
- Refresh: manual (Home → Refresh in Desktop) for local demo use; no scheduled refresh exists
  without Power BI Service + a gateway (see below).
- Power BI Desktop bundles its own PostgreSQL driver (Npgsql) in recent versions — if Get Data
  prompts for one anyway, install the official driver from postgresql.org only.

## Data model notes (apply to every report)

- Identify each imported view as either a **dimension-like table** (one row per entity —
  `powerbi_summary`, `powerbi_funnel_summary`, `stores`) or a **fact-like table** (one row per
  entity per period — `powerbi_trends`, `powerbi_sales_summary`). Relationships below are always
  1-(dimension) to *-(fact) on the natural key already used as that view's join key in SQL — never
  many-to-many.
- Set data types explicitly on import: `*_id` columns as Text (never inferred as a number), date
  columns as Date, `*_usd`/`revenue`/`amount` columns as Fixed Decimal Number formatted as
  Currency, `*_rate`/`*_ratio`/`pct_*` columns as Decimal Number formatted as Percentage.
- Hide raw key columns used only for relationships (e.g. `location_id`, `store_id`) from report
  view once the relationship is built and a friendly `name` column exists to slice/label by
  instead.
- Every measure below is written once, centrally, and reused across pages — never redefine the
  same calculation differently on two pages.

---

## Report 1 — Climate Risk & Business Impact

**Tables** (Get Data → PostgreSQL, pick these 3 views): `climate_risk.powerbi_summary` (dimension:
1 row/location), `climate_risk.powerbi_trends` (fact: 1 row/location/month),
`climate_risk.powerbi_financial_impact` (fact: 1 row/location/year/scenario).

**Relationships**: `powerbi_summary[location_id]` (1) → `powerbi_trends[location_id]` (*) ·
`powerbi_summary[location_id]` (1) → `powerbi_financial_impact[location_id]` (*).

**Measures**:
```dax
Total Business Exposure = SUM(powerbi_summary[asset_value_usd])
Avg Risk Score = AVERAGE(powerbi_summary[latest_risk_score])
High Risk Location Count = COUNTROWS(FILTER(powerbi_summary, powerbi_summary[latest_risk_score] >= 60))
Total Estimated Impact = SUM(powerbi_financial_impact[estimated_impact_usd])
Avg Temp Max (C) = AVERAGE(powerbi_trends[avg_temp_max_c])
Avg Temp Min (C) = AVERAGE(powerbi_trends[avg_temp_min_c])
Total Precipitation (mm) = SUM(powerbi_trends[total_precipitation_mm])
Avg Wind Speed (km/h) = AVERAGE(powerbi_trends[max_windspeed_kmh])
```
(`High Risk Location Count` threshold of 60/100 matches this project's own risk-score scale,
documented in `docs/methodology_climate_risk.md` — not an arbitrary Power BI-only cutoff.)

**Pages** (header band + footer per the design system above on every page):
1. **Executive Overview** — KPI cards: Total Business Exposure, Avg Risk Score, High Risk
   Location Count, Total Estimated Impact; a bar chart of `latest_risk_score` by `name` (color
   scale blue→amber→red by score); one sentence of business-impact interpretation as a text box
   ("Locations above 60 face materially elevated estimated financial exposure — see page 3").
2. **Climate Trends** — line charts of Avg Temp Max/Min and Total Precipitation over `month`;
   date-range and `location_id` slicers on this page only.
3. **Risk & Business Impact** — bar chart of `latest_risk_score` by location with conditional
   formatting (amber ≥ 40, red ≥ 60); `estimated_impact_usd` by location sliced by `scenario`; a
   text box explaining the risk-score formula (copy from `docs/methodology_climate_risk.md`, not
   re-derived).
4. **Detailed Analysis** — a table of all locations (`powerbi_summary`) with tooltips showing
   that location's monthly trend (via a Power BI tooltip page, or a simple secondary table if
   tooltip pages aren't practical to hand-configure) and industry/asset-value columns visible.

---

## Report 2 — Dark Store Intelligence

**Tables**: `dark_store.powerbi_sales_summary` (fact: 1 row/store/day),
`dark_store.powerbi_inventory_summary` (fact: 1 row/store/product),
`dark_store.powerbi_store_performance` (fact: 1 row/store/month).

**Relationships**: all three share `store_id`/`store_name` — build a small `Stores` dimension
(distinct `store_id`/`store_name`/`region`/`country` from any one view, e.g. via Power Query
"Reference" + "Remove Duplicates") and relate 1-to-* into each fact table, rather than relating
the three fact tables directly to each other.

**Measures**:
```dax
Total Revenue = SUM(powerbi_sales_summary[revenue])
Total Orders = SUM(powerbi_sales_summary[orders_count])
Avg Order Value = DIVIDE([Total Revenue], [Total Orders])
Total Profit (Est.) = SUM(powerbi_store_performance[profit_estimate])
Avg ROI % = AVERAGE(powerbi_store_performance[roi_pct])
Avg Turnover Ratio = AVERAGE(powerbi_inventory_summary[turnover_ratio])
Total Stockout Days = SUM(powerbi_inventory_summary[stockout_days])
Avg Days of Supply = AVERAGE(powerbi_inventory_summary[days_of_supply])
```

**Pages**:
1. **Executive Overview** — cards: Total Revenue, Total Orders, Avg Order Value, Total Profit
   (Est.); revenue-by-store bar (green where `roi_pct` > 0, red where negative); one-line summary
   text box. Label clearly: revenue/orders are **real** (UCI Online Retail II); profit/ROI are
   **estimated** from synthetic cost assumptions (`docs/methodology_dark_store.md`).
2. **Sales Performance** — revenue trend over `metric_date`; revenue by store/region; date and
   store slicers.
3. **Product & Inventory Intelligence** — from `powerbi_inventory_summary`: turnover ratio and
   days-of-supply by product (top/bottom 10 = fast/slow movers), stockout days by store. Text
   note: *"Inventory levels are a simulation seeded from real observed demand, not measured stock
   — see docs/methodology_dark_store.md."*
4. **Store Performance** — profit/ROI by store and month from `powerbi_store_performance`, with
   the same real-vs-estimated disclosure repeated (never assume a reader saw page 1's caption).

Do **not** add a customer-level page: the underlying UCI dataset has a `customer_id`, but no
`powerbi_*` view currently aggregates by customer, and fabricating one for this guide would
violate the "don't present unsupported metrics" instruction — if a customer view is wanted, add
`dark_store.powerbi_customer_summary` to `sql/006_powerbi_views.sql` first (real work, not a
guide-only addition), then extend this page.

---

## Report 3 — AI Hiring Bias Detector

**Tables**: `hiring_bias.powerbi_funnel_summary` (dimension-like: 1 row/`role_family`),
`hiring_bias.powerbi_fairness_summary` (fact: 1 row/attribute/group/stage),
`hiring_bias.powerbi_group_comparison` (fact: same grain + `rate_difference`/
`fails_four_fifths_rule` precomputed in SQL).

**Relationships**: none required between these three — each is independently sliceable by
`role_family` / `group_attribute` / `stage`; a synthetic bridge relationship would be artificial
and is deliberately not built (a many-to-many via `role_family` would exist between
`funnel_summary` and the other two but nothing in this data actually needs that cross-filter, so
it's correctly left out rather than added "just in case").

**Measures**:
```dax
Total Applications = SUM(powerbi_funnel_summary[total_applications])
Total Screened = SUM(powerbi_funnel_summary[reached_screen])
Total Interviewed = SUM(powerbi_funnel_summary[reached_interview])
Total Offered = SUM(powerbi_funnel_summary[reached_offer])
Total Hired = SUM(powerbi_funnel_summary[reached_hire])
Screen Rate = DIVIDE([Total Screened], [Total Applications])
Interview Rate = DIVIDE([Total Interviewed], [Total Screened])
Offer Rate = DIVIDE([Total Offered], [Total Interviewed])
Hire Rate = DIVIDE([Total Hired], [Total Offered])
Overall Selection Rate = DIVIDE([Total Hired], [Total Applications])
Groups Failing 4/5ths Rule = CALCULATE(DISTINCTCOUNT(powerbi_group_comparison[group_value]), powerbi_group_comparison[fails_four_fifths_rule] = TRUE)
```
Selection rate and adverse-impact ratio *per group* are already computed in SQL
(`002_fairness_metrics.sql`) and exposed as plain columns on `powerbi_group_comparison` —
visualize those columns directly rather than re-deriving them in DAX, so Power BI can never
disagree with the SQL model or the Streamlit dashboard.

**Pages**:
1. **Executive Overview** — cards: Total Applications, Screen Rate, Interview Rate, Offer Rate,
   Hire Rate, Overall Selection Rate, Groups Failing 4/5ths Rule (amber/red if > 0); a prominent
   text banner: *"100% synthetic data with documented, adjustable bias injection — see
   docs/methodology_hiring_bias.md. Not evidence about any real employer."*
2. **Recruitment Funnel** — a funnel or stepped-bar chart of the five stage totals; conversion
   rates as a secondary table; `role_family` slicer (the only breakdown dimension this dataset
   has — no department/location field exists, so none is shown here, matching the "where
   available" qualifier in the report-structure spec).
3. **Fairness & Group Comparison** — selection rate by group and stage (grouped bar, neutral
   qualitative colors per the design system); `adverse_impact_ratio` with a reference line at 0.8;
   red/amber conditional formatting only on rows where `fails_four_fifths_rule` is true.
4. **Model & Decision Analysis** — `audit_model_coefficients` (not yet a `powerbi_*` view — add
   one, e.g. `hiring_bias.powerbi_audit_coefficients`, before building this page) showing each
   feature's coefficient and confidence interval; text notes: this model is interpretability-only,
   was never used to score or rank any candidate, and a coefficient's sign/size describes
   association within this synthetic dataset only, not a causal or real-world claim; ethical-use
   disclaimer copied from `docs/methodology_hiring_bias.md`.

**This report must never rank or recommend individual candidates** — every page here aggregates
at the group/stage/role level; no per-candidate table or score should ever be added to it.

---

## Report 4 — Fraud Pattern Evolution Tracker

**Tables**: `fraud_pattern.powerbi_risk_summary` (single-row model+volume snapshot),
`fraud_pattern.powerbi_trends` (fact: 1 row/month), `fraud_pattern.powerbi_network_summary`
(fact: 1 row/account).

**Relationships**: none required — `powerbi_risk_summary` is a single-row summary table (no key
to relate on); `powerbi_trends` and `powerbi_network_summary` are independently sliceable.

**Measures**:
```dax
Total Transactions = SUM(powerbi_risk_summary[total_transactions])
Flagged Transactions = SUM(powerbi_risk_summary[flagged_transactions])
True Fraud Transactions = SUM(powerbi_risk_summary[true_fraud_transactions])
True Fraud Rate = AVERAGE(powerbi_risk_summary[true_fraud_rate])
Model Precision = AVERAGE(powerbi_risk_summary[precision])
Model Recall = AVERAGE(powerbi_risk_summary[recall])
Model ROC AUC = AVERAGE(powerbi_risk_summary[roc_auc])
Ring Candidate Accounts = CALCULATE(DISTINCTCOUNT(powerbi_network_summary[account_id]), powerbi_network_summary[is_ring_candidate] = TRUE)
Avg Cluster Size = AVERAGE(powerbi_network_summary[component_size])
```
`Model Precision`/`Model Recall`/`Model ROC AUC` are single-model-run outputs already computed in
Python/scikit-learn against real ground truth (`evaluate_model_and_load()`) — expose as cards,
never recompute a classification metric inside DAX.

**Pages**:
1. **Executive Overview** — cards: Total Transactions, Flagged Transactions, True Fraud
   Transactions, True Fraud Rate, Model ROC AUC; banner: *"100% synthetic transactions with
   injected fraud rings — ground truth is known by construction, so these model metrics are real,
   not illustrative. See docs/methodology_fraud_pattern.md."*
2. **Fraud Trends** — `fraud_rate` and `fraud_amount` over `month` from `powerbi_trends`; a
   month-range slicer.
3. **Detection Performance** — Model Precision/Recall/ROC AUC as large cards, plus a short text
   box explaining *why* precision is low at this threshold (copy the exact explanation from
   `docs/methodology_fraud_pattern.md`'s "Observed results" section — do not soften or omit it).
   A confusion-matrix visual is not built here: no `powerbi_*` view currently exposes true/false
   positive/negative counts (only the aggregate metrics), so add one (e.g. extend
   `powerbi_risk_summary` or add a small `powerbi_confusion_matrix` view) before adding that
   visual — do not approximate a confusion matrix from precision/recall alone in DAX.
4. **Pattern & Network Analysis** — a **table** (not a fabricated network diagram — Power BI has
   no first-party reliable force-directed graph visual, and this dataset's connectivity is exactly
   what `powerbi_network_summary` already answers) of ring-candidate accounts sorted by
   `component_size`/`degree`, with `is_fraud_ring_member`/`ring_id` columns visible for direct
   ground-truth comparison.

State on every page that all transaction/account data is synthetic — this project has no real
transaction data at all (see `docs/data_sources.md`).

---

## Power BI Service publication: BLOCKED

Requires, at minimum: (1) a Power BI account with write access to a workspace, and (2) for a
report backed by a local (non-cloud) Postgres instance, either an **On-premises Data Gateway**
reachable from that workspace, or accepting manual-refresh-only (no scheduled refresh). Neither a
Power BI account/workspace nor a gateway exists in this environment, and provisioning either is an
account-level decision this session cannot make or configure safely. To do this yourself: sign in
to Power BI Desktop (top-right "Sign in"), confirm a workspace under **Workspaces**, then
**File → Publish → Publish to Power BI**; for a gateway, see
https://learn.microsoft.com/power-bi/connect-data/service-gateway-onprem.

## Troubleshooting

- **Get Data → PostgreSQL fails to connect**: confirm the Docker stack is running
  (`docker compose ps` in the repo root) and port 5433 is reachable (`Test-NetConnection localhost
  -Port 5433` in PowerShell).
- **A view returns 0 rows**: its owning DAG hasn't completed a run yet — trigger it (see
  `README.md`) and wait; `dark_store_pipeline` in particular takes ~30 minutes.
- **A measure's value doesn't match the Streamlit dashboard**: it shouldn't ever happen if you
  used the exact DAX above (every measure reads directly from a `powerbi_*` view column, and those
  views are pure passthroughs of the same tables the dashboards query) — if it does, that's a real
  bug; check for an accidental extra filter/slicer active on the page before assuming the DAX
  itself is wrong.

## Known limitations

- No report file has been created or validated in Power BI Desktop itself (see Status above) —
  everything in this guide is a specification, reconciled on paper against already-verified SQL,
  not an artifact confirmed to load, render, or respond to filters correctly.
- Two measures per report (hiring's audit-coefficients page, fraud's confusion matrix) call for a
  `powerbi_*` view that doesn't exist yet — flagged explicitly above rather than silently
  approximated from data that can't actually answer the question.
- No Power BI Service publication attempted (account/workspace/gateway don't exist here).
