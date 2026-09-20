"""One-time migration: push each project's real H2O AutoML leaderboard into
its own schema in the shared Neon database, so the new automl/app.py pages
have something to read.

Source data (all real, nothing fabricated):
  - h2o_saved_models/leader_summary.json -- target_column, project_name
  - h2o_saved_models/*  (model binaries, excluding .json/.csv) -- the exact,
    untruncated model_id for every model H2O trained, in the order H2O's
    save loop wrote them (confirmed via file mtime), which is the same
    order as aml.leaderboard (the save loop iterates
    aml.leaderboard["model_id"] directly) -- so mtime order == leaderboard
    rank order.
  - the notebook's own aml.leaderboard cell output (text/html, parsed with
    pandas.read_html) -- the real per-model metric columns H2O computed.
    Its own model_id column is display-truncated for long names, so it is
    NOT used for identity -- only as a cross-check (every truncated value
    must be a prefix of the corresponding on-disk model_id, in the same
    row order) before trusting the numeric columns next to it.

Run once, manually, with ANALYTICS_DATABASE_URL set to the shared Neon
connection string (not committed anywhere -- see neon.txt kept outside any
repo), e.g.:

    ANALYTICS_DATABASE_URL="postgresql://..." python scripts/migrate_automl_leaderboard.py

Not part of any DAG -- each project's automl_leaderboard table is a static
snapshot of one AutoML run, not something a recurring pipeline recomputes.
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.database import get_engine  # noqa: E402

REPOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "standalone-repos")

ALGORITHM_FAMILIES = ["StackedEnsemble", "DeepLearning", "GBM", "DRF", "XRT", "GLM"]

LEADERBOARD_METRIC_COLUMNS = [
    "auc", "logloss", "aucpr", "mean_per_class_error",
    "mae", "rmse", "mse", "rmsle", "mean_residual_deviance",
]

PROJECTS = {
    "fraud_pattern": {
        "repo_dir": os.path.join(REPOS_DIR, "fraud-pattern-evolution-tracker"),
        "notebook": "fraud_model_comparison.ipynb",
        "leaderboard_cell_index": 23,
    },
    "climate_risk": {
        "repo_dir": os.path.join(REPOS_DIR, "climate-risk-business-impact-analyzer"),
        "notebook": "climate_risk_model.ipynb",
        "leaderboard_cell_index": 29,
    },
    "dark_store": {
        "repo_dir": os.path.join(REPOS_DIR, "dark-store-intelligence-dashboard"),
        "notebook": "demand_forecast_model.ipynb",
        "leaderboard_cell_index": 30,
    },
    "hiring_bias": {
        "repo_dir": os.path.join(REPOS_DIR, "ai-hiring-bias-detector"),
        "notebook": "hiring_bias_model_comparison.ipynb",
        "leaderboard_cell_index": 28,
    },
}


def _algorithm_for(model_id: str) -> str:
    for family in ALGORITHM_FAMILIES:
        if model_id.startswith(family):
            return family
    raise ValueError(f"unrecognized H2O algorithm prefix for model_id {model_id!r}")


def _ordered_model_ids(model_dir: str) -> list[str]:
    """Real, untruncated model_id values in H2O's save-loop (== leaderboard
    rank) order, recovered from file mtime -- see module docstring."""
    entries = []
    for fname in os.listdir(model_dir):
        path = os.path.join(model_dir, fname)
        if not os.path.isfile(path) or fname.endswith(".json") or fname.endswith(".csv"):
            continue
        entries.append((os.path.getmtime(path), fname))
    entries.sort(key=lambda t: t[0])
    return [fname for _, fname in entries]


def _leaderboard_df(notebook_path: str, cell_index: int) -> pd.DataFrame:
    with open(notebook_path, encoding="utf-8") as f:
        nb = json.load(f)
    cell = nb["cells"][cell_index]
    for out in cell.get("outputs", []):
        if out.get("output_type") == "execute_result" and "text/html" in out.get("data", {}):
            html = "".join(out["data"]["text/html"])
            df = pd.read_html(io.StringIO(html))[0]
            return df.drop(columns=[c for c in df.columns if str(c).startswith("Unnamed")])
    raise ValueError(f"no leaderboard execute_result found in cell {cell_index}")


def extract_project(project_schema: str, cfg: dict) -> pd.DataFrame:
    model_dir = os.path.join(cfg["repo_dir"], "h2o_saved_models")
    notebook_path = os.path.join(cfg["repo_dir"], cfg["notebook"])

    with open(os.path.join(model_dir, "leader_summary.json")) as f:
        summary = json.load(f)

    full_ids = _ordered_model_ids(model_dir)
    lb = _leaderboard_df(notebook_path, cfg["leaderboard_cell_index"])

    if len(full_ids) != len(lb):
        raise ValueError(
            f"{project_schema}: {len(full_ids)} saved models on disk but "
            f"{len(lb)} leaderboard rows -- refusing to guess the mapping"
        )
    for full_id, truncated in zip(full_ids, lb["model_id"]):
        stem = str(truncated).rstrip(".")  # pandas truncates long strings with "..."
        if not full_id.startswith(stem):
            raise ValueError(
                f"{project_schema}: on-disk model_id {full_id!r} does not "
                f"match leaderboard row {truncated!r} at the same position "
                "-- mtime order and leaderboard order have diverged"
            )

    rows = []
    model_mtime = {
        fname: os.path.getmtime(os.path.join(model_dir, fname))
        for fname in full_ids
    }
    for rank, (full_id, (_, lb_row)) in enumerate(zip(full_ids, lb.iterrows()), start=1):
        row = {
            "model_id": full_id,
            "algorithm": _algorithm_for(full_id),
            "rank": rank,
            "is_leader": full_id == summary["leader_model_id"],
            "target_column": summary["target_column"],
            "project_name": summary["project_name"],
            "trained_at": datetime.fromtimestamp(model_mtime[full_id], tz=timezone.utc),
        }
        for col in LEADERBOARD_METRIC_COLUMNS:
            val = lb_row.get(col)
            row[col] = None if val is None or (isinstance(val, float) and pd.isna(val)) else float(val)
        rows.append(row)

    df = pd.DataFrame(rows)
    if not (df["is_leader"].sum() == 1 and bool(df.loc[df["rank"] == 1, "is_leader"].iloc[0])):
        raise ValueError(f"{project_schema}: leader_summary's leader_model_id is not rank 1 -- investigate")
    return df


def main() -> None:
    engine = get_engine()
    counts = {}
    for schema, cfg in PROJECTS.items():
        df = extract_project(schema, cfg)
        columns = list(df.columns)
        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        update_cols = [c for c in columns if c != "model_id"]
        update_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
        stmt = (
            f'INSERT INTO "{schema}"."automl_leaderboard" ({col_list}) VALUES ({placeholders}) '
            f'ON CONFLICT ("model_id") DO UPDATE SET {update_clause}'
        )
        records = df.to_dict(orient="records")
        with engine.begin() as conn:
            conn.execute(text(stmt), records)
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."automl_leaderboard"')).scalar()
        counts[schema] = count
        print(f"{schema}.automl_leaderboard: wrote {len(records)} rows, table now has {count} rows")
        print(f"  leader: {df.loc[df['rank'] == 1, 'model_id'].iloc[0]}")

    print()
    print("Row counts:", counts)


if __name__ == "__main__":
    main()
