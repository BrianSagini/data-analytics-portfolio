# How I built this, and what I verified

This is the build log I actually want a reader to see — what I built, what broke, and how I know
it works — instead of a phase-by-phase audit checklist. If you want the raw pass/fail detail this
was distilled from, it's still in git history; I removed it from the working docs because keeping
a QA log next to the actual project made the repo read like a test report instead of a portfolio.

## Infrastructure

Everything runs in its own isolated Docker Compose stack — Postgres 16 on a non-default port
(5433), Airflow 3.3.1 on LocalExecutor, four Streamlit containers — chosen deliberately so it
never collides with anything else already running on the machine I built this on. A few real
things came up getting it stable:

- Postgres 15+ stopped granting `CREATE` on the `public` schema to new roles by default, which
  broke Airflow's own metadata migration on first boot. Fixed with an explicit grant in the init
  script.
- Exact version pins in `airflow/requirements.txt` (`pandas`, `sqlalchemy`, `requests`,
  `scikit-learn`) were fighting Airflow's own provider requirements. Switched to floor constraints
  so nothing the base image already satisfies gets force-downgraded.
- Docker's engine crashed once mid-build (`docker ps` returning `500 Internal Server Error`).
  Postgres and Airflow came back on their own (`restart: unless-stopped`); the four dashboard
  containers didn't, so I brought those back up by hand and confirmed row counts matched what they
  were before the crash — nothing lost. That same crash knocked out that day's scheduled DAG runs
  (their first task's network call landed mid-crash); re-triggered all four once the stack was
  stable again.

## Real bugs I found and fixed while verifying, not just while building

- `fraud_pattern.model_evaluation.computed_at` was staying frozen at its very first insert forever
  — the upsert function never included that column in the data it wrote, so `ON CONFLICT DO
  UPDATE` had nothing to refresh it with. Every rerun silently kept claiming the first-ever
  timestamp. Found by comparing the column's value against the DAG run that had just finished;
  fixed by setting it explicitly in the write path, then checked every other project for the same
  shape of bug (none had it — their timestamps are set in SQL's own `ON CONFLICT` clause, which
  already refreshes correctly).
- The fraud dashboard had zero interactive filter widgets — added a severity filter.
- A browser-test script initially undercounted Dark Store's charts; the dashboard itself was fine,
  the test just wasn't waiting long enough for everything to draw.

## Verification

**Airflow**: all four DAGs run end to end against real, timestamped runs (6–30 minutes each,
Dark Store is the slow one because it parses a real ~45MB spreadsheet). Confirmed by querying
Airflow's own metadata database directly, not just trusting the CLI.

**Dashboards**: real headless-Chromium testing (Playwright) against all four — page load, chart
and metric rendering, a real filter interaction, zero console/JS errors, and a narrow-viewport
render. Screenshots in `scripts/browser_test_screenshots/`, full detail in
`docs/browser_testing.md`.

**KPIs**: I picked one KPI per project and traced it through all three layers — the SQL query, the
Power BI view built on top of it, and what the live dashboard actually displays:

| Project | KPI | SQL | Power BI view | Dashboard | Match |
|---|---|---|---|---|---|
| Dark Store | Total revenue / orders | $10,667,354.24 / 19,960 | same | $10,667,354 / 19,960 | exact |
| Fraud | Precision / recall / ROC-AUC | 0.1161 / 0.7794 / 0.9268 | same | 0.12 / 0.78 / 0.93 (rounded) | exact |
| Climate | Top-3 moderate-scenario impact | Houston $17.0M, NYC $7.58M, Phoenix $6.0M | same | same ranking/values | exact |
| Hiring | Gender adverse-impact ratio @ hire | Man 0.895, Non-binary 1.0, Woman 0.984 | same + derived flag | same | exact |

The Power BI views are pure passthrough queries over the same tables the dashboards read, so this
match is guaranteed by construction — I verified it anyway rather than assuming it.

## Power BI: how the reports actually got built

I hand-authored the `.pbip`/TMDL/PBIR files rather than generating a placeholder, which meant
finding out the hard way what Power BI Desktop actually requires versus what its schema docs
imply. In rough order:

1. First pass had the full data model and zero visuals. Once I added real visuals, every chart
   rendered blank, titles didn't show, currency showed a stray `\$`, and dates showed full weekday
   text instead of a month. Root causes: a missing `active: true` on chart category fields, titles
   in the wrong JSON location, a literal backslash in a format string, and a lowercase `mm`
   (minutes) where `MM` (month) belonged. Found by diffing Power BI Desktop's own re-save of the
   file against my prior version.
2. A tenant policy disabled map visuals entirely ("Map and filled map visuals aren't enabled for
   your org") — no file fix possible, so I replaced every map with an equivalent data table.
3. After adding a custom theme and per-visual accent colors, chart Y-fields that referenced a raw
   column instead of an aggregated one rendered as a completely empty plot area — no error, no
   warning, just nothing. Confirmed by switching a chart's visual type and watching Desktop
   auto-insert the aggregation wrapper it needed; fixed the same way across every chart in the
   portfolio.
4. Card visuals used the wrong JSON object for their accent color (`dataPoint`, which is really a
   chart property) — Desktop silently drops it from a card on load, so the color just never
   applied. The real property is `objects.labels[...].properties.color`.
5. The report background I'd set in round 3 turned out to not be the property that actually
   colors the canvas — `outspace` isn't it. Confirmed the real one live in Desktop (set a color
   through the theme customizer, saved, read back what Desktop wrote): `visualStyles.page.*.background`.
   Every project's canvas is now visibly its own tinted color instead of a near-invisible wash.
6. Fraud Pattern Evolution's four pages ran as sparse as 48% full by visual area, and two of them
   turned out to duplicate a table and a KPI card outright. Merged those two pages into one, and
   merged the other two into a trend-plus-pattern pairing that suits a report named "Pattern
   Evolution" better split across four thinner pages.

Every one of those fixes was confirmed by actually reopening the file in Power BI Desktop and
watching the page render correctly, not by re-reading the JSON and hoping. Screenshots are in each
project's `docs/evidence/`.

One safety note worth keeping: an early screenshot attempt captured live desktop content that had
nothing to do with Power BI, and a later one caught the wrong window because focus had shifted.
Both were deleted immediately and never committed. Every capture after that went through a script
that verifies the Power BI window is actually in focus immediately before *and* after taking the
screenshot, aborting with no file written if either check fails — it did abort correctly at least
twice during the real runs, which is exactly what it was there to catch.

## What's still not done

- Two Power BI pages (Hiring's audit-coefficients breakdown, Fraud's confusion-matrix breakdown)
  use the real fields available today instead of the SQL views I'd need to build for their
  originally-envisioned content.
- Publishing to the Power BI Service itself is untested — that needs an account, workspace, and
  (for a local Postgres source) an on-premises data gateway, none of which exist in this setup.
- This monorepo has no GitHub remote by design — the four projects inside it are published as
  independent, fully self-contained repos instead (see the table in `README.md`), which is where
  I'd point anyone wanting to see one in isolation.

None of that blocks running the four pipelines and dashboards locally, which is what this repo is
for.
