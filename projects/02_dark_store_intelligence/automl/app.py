"""Dark Store Intelligence -- H2O AutoML results.

Not the H2O Flow UI itself (that needs a running JVM cluster, which isn't
feasible on free Streamlit hosting) -- this reads the real leaderboard H2O
AutoML produced in demand_forecast_model.ipynb's "AutoML sanity check (H2O)"
section, persisted to dark_store.automl_leaderboard since the original
aml.leaderboard object doesn't survive that notebook's session.
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

st.set_page_config(page_title="Dark Store -- AutoML Results", layout="wide")
st.title("🤖 Dark Store Intelligence -- H2O AutoML Results")
st.caption(
    "A static snapshot of one H2O AutoML run predicting units_demanded -- GLM/GBM/DRF/"
    "DeepLearning/StackedEnsemble search, sorted by MAE (lower is better). This is the "
    "leaderboard, not a live Flow session: H2O needs a JVM cluster, which free hosting here "
    "doesn't provide."
)


@st.cache_data(ttl=300)
def load(query: str) -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(text(query), engine)


try:
    leaderboard = load("SELECT * FROM dark_store.automl_leaderboard ORDER BY rank")
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not connect to the analytics database: {exc}")
    st.stop()

if leaderboard.empty:
    st.warning("No AutoML results yet -- run the migration that loads dark_store.automl_leaderboard.")
    st.stop()

leader = leaderboard.iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Best model", leader["algorithm"])
col2.metric("MAE", f"{leader['mae']:.2f}")
col3.metric("RMSE", f"{leader['rmse']:.2f}")
col4.metric("Models searched", len(leaderboard))
st.caption(f"Target: `{leader['target_column']}` · trained {leader['trained_at']:%Y-%m-%d %H:%M UTC}")

st.subheader("Leaderboard")
display = leaderboard[["rank", "model_id", "algorithm", "mae", "rmse", "mean_residual_deviance"]].rename(
    columns={
        "rank": "Rank", "model_id": "Model ID", "algorithm": "Algorithm", "mae": "MAE",
        "rmse": "RMSE", "mean_residual_deviance": "Mean residual deviance",
    }
)
st.dataframe(
    display.style.apply(lambda row: ["background-color: #fff3cd" if row["Rank"] == 1 else "" for _ in row], axis=1)
    .format({"MAE": "{:.2f}", "RMSE": "{:.2f}", "Mean residual deviance": "{:.2f}"}),
    use_container_width=True, hide_index=True,
)

st.subheader("MAE by model")
fig = px.bar(
    leaderboard.sort_values("rank"), x="model_id", y="mae", color="algorithm",
    title="H2O AutoML leaderboard -- MAE by model (lower is better)",
    labels={"model_id": "Model", "mae": "MAE", "algorithm": "Algorithm"},
)
fig.update_xaxes(showticklabels=False)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Why this differs from the main model comparison"):
    st.markdown(
        """
        This AutoML leaderboard's MAE is H2O's own cross-validation score during training, not
        the held-out test-set score. The main dashboard's `model_evaluation` numbers (and
        `demand_forecast_model.ipynb`'s own write-up) score the actual held-out test set --
        that real result is **MAE 15.59, RMSE 67.26**, computed separately in the notebook
        against the real test split, not reproduced here. The two numbers measure different
        things on purpose; see `docs/model_card.md` in the dark-store repo for the full comparison.
        """
    )
