"""AI Hiring Bias Detector -- H2O AutoML results.

Not the H2O Flow UI itself (that needs a running JVM cluster, which isn't
feasible on free Streamlit hosting) -- this reads the real leaderboard H2O
AutoML produced in hiring_bias_model_comparison.ipynb's "AutoML sanity
check (H2O)" section, persisted to hiring_bias.automl_leaderboard since the
original aml.leaderboard object doesn't survive that notebook's session.

Like the rest of this project, this is a fairness AUDIT view -- H2O's
leader is never used to score, rank, or decide on any candidate.
"""
from __future__ import annotations

import os
import sys

# Streamlit Community Cloud runs this file directly from its own location
# with no PYTHONPATH set (unlike docker-compose locally), so the repo root
# -- where shared/ lives -- isn't on sys.path without this.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from shared.database import get_engine

st.set_page_config(page_title="Hiring -- AutoML Results", layout="wide")
st.title("🤖 AI Hiring Bias Detector -- H2O AutoML Results")
st.caption(
    "A static snapshot of one H2O AutoML run over the exact same one-hot-encoded, standardized "
    "features and stratified train/test split as the audit model -- GLM/GBM/DRF/XRT/DeepLearning/"
    "StackedEnsemble search, sorted by AUC. This is the leaderboard, not a live Flow session: H2O "
    "needs a JVM cluster, which free hosting here doesn't provide."
)


@st.cache_data(ttl=300)
def load(query: str) -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(text(query), engine)


try:
    leaderboard = load("SELECT * FROM hiring_bias.automl_leaderboard ORDER BY rank")
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not connect to the analytics database: {exc}")
    st.stop()

if leaderboard.empty:
    st.warning("No AutoML results yet -- run the migration that loads hiring_bias.automl_leaderboard.")
    st.stop()

leader = leaderboard.iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Best model", leader["algorithm"])
col2.metric("AUC", f"{leader['auc']:.4f}")
col3.metric("Log loss", f"{leader['logloss']:.4f}")
col4.metric("Models searched", len(leaderboard))
st.caption(f"Target: `{leader['target_column']}` · trained {leader['trained_at']:%Y-%m-%d %H:%M UTC}")

st.subheader("Leaderboard")
display = leaderboard[["rank", "model_id", "algorithm", "auc", "logloss", "aucpr", "mean_per_class_error", "rmse"]].rename(
    columns={
        "rank": "Rank", "model_id": "Model ID", "algorithm": "Algorithm", "auc": "AUC",
        "logloss": "Log loss", "aucpr": "AUC-PR", "mean_per_class_error": "Mean per-class error", "rmse": "RMSE",
    }
)
st.dataframe(
    display.style.apply(lambda row: ["background-color: #fff3cd" if row["Rank"] == 1 else "" for _ in row], axis=1)
    .format({"AUC": "{:.4f}", "Log loss": "{:.4f}", "AUC-PR": "{:.4f}", "Mean per-class error": "{:.4f}", "RMSE": "{:.4f}"}),
    use_container_width=True, hide_index=True,
)

st.subheader("AUC by model")
fig = px.bar(
    leaderboard.sort_values("rank"), x="model_id", y="auc", color="algorithm",
    title="H2O AutoML leaderboard -- AUC by model (higher is better)",
    labels={"model_id": "Model", "auc": "AUC", "algorithm": "Algorithm"},
)
fig.update_xaxes(showticklabels=False)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Why this differs from the main model comparison"):
    st.markdown(
        """
        This AutoML leaderboard's AUC is H2O's own cross-validation score during training, not
        the held-out test-set score. The main dashboard's audit model (and
        `hiring_bias_model_comparison.ipynb`'s own write-up) score the actual held-out test set --
        that real result is **0.6272 ROC-AUC** for H2O's leader (a plain GLM), effectively
        identical to the hand-picked logistic regression's **0.6271** on the same split. An
        automated search across 45 models and six algorithm families doesn't find materially more
        ranking signal than the simple interpretable model this project already uses -- see
        `docs/model_card.md` in the hiring repo for the full comparison.
        """
    )

with st.expander("What this is not"):
    st.markdown(
        """
        - **Not a hiring decision tool.** Every model on this leaderboard was trained only to
          check whether the interpretable audit model's modest ranking signal holds up against an
          automated search -- none of them score, rank, or recommend any candidate.
        - **All data is 100% synthetic**, with deliberately injected and exaggerated bias -- see
          `docs/methodology.md`.
        """
    )
