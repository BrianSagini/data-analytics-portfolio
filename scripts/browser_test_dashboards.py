"""Real browser smoke test for all 4 Streamlit dashboards, using Playwright.

Run manually (not part of any Airflow DAG or CI): each dashboard must
already be up (docker compose up -d dashboard-*). Not a pytest suite --
this drives a real Chromium instance and captures screenshots + console
errors as evidence for docs/browser_testing.md, since "started without
errors in container logs" (checked earlier in this build) is not the
same claim as "a real browser loaded it and the UI works."
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path(__file__).parent / "browser_test_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

DASHBOARDS = [
    {"name": "climate", "url": "http://localhost:8501", "title_contains": "Climate Risk"},
    {"name": "darkstore", "url": "http://localhost:8502", "title_contains": "Dark Store"},
    {"name": "hiring", "url": "http://localhost:8503", "title_contains": "Hiring Bias"},
    {"name": "fraud", "url": "http://localhost:8504", "title_contains": "Fraud"},
]


def test_dashboard(playwright, spec: dict) -> dict:
    result = {"name": spec["name"], "url": spec["url"], "console_errors": [], "page_errors": []}
    browser = playwright.chromium.launch()
    try:
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.on("console", lambda msg: result["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: result["page_errors"].append(str(exc)))

        page.goto(spec["url"], wait_until="domcontentloaded", timeout=45000)
        # Streamlit renders over a persistent WebSocket after the initial HTML
        # shell loads, so "networkidle" fires before real content exists (an
        # earlier run of this script caught a screenshot of nothing but the
        # loading skeleton). Wait for the page title (always an <h1> from
        # st.title()) specifically -- it's the most reliable "real content
        # has arrived" signal, and a cold first query can take a while.
        page.wait_for_selector("h1", timeout=45000)
        # Pages backed by several sequential SQL queries (e.g. dark store: 5
        # queries over up to 519k rows) can take several seconds after the
        # title appears before every chart has actually drawn -- empirically
        # confirmed 2.5s under-counted charts that were present at 15s.
        page.wait_for_timeout(9000)

        body_text = page.inner_text("body")
        result["title_found"] = spec["title_contains"] in body_text
        result["has_content"] = len(body_text.strip()) > 200

        # Plotly.js always draws an SVG with class "main-svg" inside its
        # container, regardless of exact wrapper markup across versions --
        # more reliable than guessing the container class name (verified
        # empirically: an earlier attempt using ".js-plotly-plot" undercounted).
        charts = page.locator("svg.main-svg").count()
        result["plotly_charts_rendered"] = charts

        metrics = page.locator('[data-testid="stMetric"], [data-testid="stMetricValue"]').count()
        result["metric_cards_rendered"] = metrics

        multiselects = page.locator('[data-baseweb="select"], [data-baseweb="tag"]').count()
        result["filter_widgets_found"] = multiselects

        page.screenshot(path=str(SCREENSHOT_DIR / f"{spec['name']}_desktop.png"), full_page=True)

        # Try a real filter interaction. These multiselects default to "all
        # selected" (see each dashboard's app.py), so opening the dropdown
        # correctly shows "No results" -- there's nothing left to add. The
        # realistic interaction is removing one already-selected tag (its "x")
        # and confirming the page re-renders with fewer categories.
        tags = page.locator('[data-baseweb="tag"]')
        radios = page.locator('[data-baseweb="radio"]')
        if tags.count() > 0:
            try:
                before = page.locator("svg.main-svg").count()
                tags.first.locator("svg, [role='presentation']").last.click()
                page.wait_for_timeout(2500)
                after = page.locator("svg.main-svg").count()
                result["filter_interaction_ok"] = f"tag_removed (charts before={before}, after={after})"
                page.screenshot(path=str(SCREENSHOT_DIR / f"{spec['name']}_after_filter.png"), full_page=True)
            except Exception as exc:  # noqa: BLE001
                result["filter_interaction_ok"] = f"error: {exc}"
        elif radios.count() > 0:
            try:
                radios.nth(1).click()
                page.wait_for_timeout(2500)
                result["filter_interaction_ok"] = "radio_switched"
                page.screenshot(path=str(SCREENSHOT_DIR / f"{spec['name']}_after_filter.png"), full_page=True)
            except Exception as exc:  # noqa: BLE001
                result["filter_interaction_ok"] = f"error: {exc}"
        else:
            result["filter_interaction_ok"] = "no_filter_widget"

        # Narrower viewport check
        page.set_viewport_size({"width": 480, "height": 900})
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOT_DIR / f"{spec['name']}_narrow.png"), full_page=True)
        result["narrow_viewport_ok"] = True

        result["status"] = "PASS" if result["has_content"] and not result["page_errors"] else "FAIL"
    except Exception as exc:  # noqa: BLE001
        result["status"] = "FAIL"
        result["exception"] = str(exc)
    finally:
        browser.close()
    return result


def main():
    results = []
    with sync_playwright() as p:
        for spec in DASHBOARDS:
            print(f"Testing {spec['name']} ({spec['url']})...", file=sys.stderr)
            results.append(test_dashboard(p, spec))
            time.sleep(1)

    out_path = Path(__file__).parent / "browser_test_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))

    if any(r["status"] != "PASS" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
