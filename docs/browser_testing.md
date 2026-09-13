# Browser Testing

Real Playwright/Chromium browser tests against all four running Streamlit dashboards — not just
"container started and logged no error" (which was all the original build verified). Script:
`scripts/browser_test_dashboards.py`. Screenshots: `scripts/browser_test_screenshots/`.
Raw results: `scripts/browser_test_results.json`.

## Method

For each dashboard: launch headless Chromium, navigate, wait for the page's `<h1>` title to
appear (Streamlit renders over a persistent WebSocket after the initial HTML shell, so
`networkidle` fires before real content exists — confirmed empirically: an early run of this
script screenshotted nothing but Streamlit's loading skeleton), wait an additional 9s for
charts/queries to finish (some pages run 4-5 sequential SQL queries over up to ~520k rows), then:
count rendered Plotly charts (`svg.main-svg`), metric cards (`[data-testid="stMetric"]`), and
filter widgets; capture a full-page desktop screenshot; **actually interact with a filter**
(remove a pre-selected tag from a multiselect, or switch a radio option) and screenshot the
result; resize to a 480px-wide viewport and screenshot again; record any browser console errors
or uncaught page exceptions.

## Results (run 2026-09-13)

| Dashboard | Title | Charts | Metrics | Filter widgets | Filter interaction | Console/page errors | Narrow viewport |
|---|---|---|---|---|---|---|---|
| Climate (:8501) | ✅ | 9 | 6 | 12 | ✅ removed a location tag, no crash | none | ✅ |
| Dark Store (:8502) | ✅ | 12 | 6 | 8 | ✅ removed a store tag, no crash | none | ✅ |
| Hiring Bias (:8503) | ✅ | 12 | 0 | 0 (radio, not select) | ✅ switched gender→ethnicity grouping | none | ✅ |
| Fraud (:8504) | ✅ | 6 | 8 | 3 | ✅ removed a severity tag, no crash | none | ✅ |

All four: **PASS**. Zero console errors, zero uncaught page exceptions, real chart/metric
content confirmed (not just a non-empty page), at least one real filter interaction performed and
confirmed not to crash the page, both desktop and narrow-viewport screenshots captured.

## Issues found and fixed during this testing pass (not fabricated results)

1. **Dark store dashboard's map/charts appeared missing at a 2.5s wait.** Root cause: this
   dashboard runs 5 sequential SQL queries over up to ~520k rows before its last chart draws;
   2.5s wasn't enough. Fixed by increasing the post-title wait to 9s and confirmed at 15s (via a
   throwaway diagnostic) that all charts do render — this was a test-script timing bug, not a
   dashboard bug. The dashboard's own code was not changed.
2. **Fraud dashboard had zero interactive filter widgets** — a real gap, not a test artifact
   (confirmed by reading `projects/04_fraud_pattern_evolution/dashboard/app.py`: no
   `st.selectbox`/`multiselect`/`radio` existed anywhere). Fixed by adding a severity multiselect
   filter on the alerts table (`app.py`), rebuilt the dashboard's Docker image, and re-verified
   the filter now works via a real interaction.
3. **Hiring dashboard's grouping control is `st.radio`, not a select/multiselect** — the test
   script's filter-interaction logic originally only handled multiselect tags; extended it to
   also detect and click a radio option.

## Known limitation of this testing pass

This confirms each dashboard loads, renders real data, responds to at least one filter without
crashing, and throws no browser-console/JS errors. It is not a full interaction matrix (every
filter combination, every chart's tooltip/zoom, accessibility) — that would need a larger,
maintained test suite, which wasn't in scope here.
