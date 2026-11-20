"""Gold-layer dashboard: streamlit run app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="NYC Taxi — Gold Dashboard", page_icon="\U0001F695",
                   layout="wide")

DATA_DIR = Path(__file__).resolve().parent / "dashboard" / "data"
USD = "$"


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        st.error(f"Missing {name} — run python -m src.export_gold first.")
        st.stop()
    return pd.read_csv(path, parse_dates=["trip_date", "refreshed_at"])


daily = load_csv("gold_daily_revenue.csv")
zones = load_csv("gold_zone_daily.csv")

st.title("\U0001F695 NYC Taxi Trips — Gold Layer Dashboard")
st.caption(
    f"Source: analytics-engineering-pipeline \u00b7 refreshed "
    f"{daily['refreshed_at'].max():%Y-%m-%d %H:%M} UTC \u00b7 {len(daily)} days"
)

total_trips = int(daily["trip_count"].sum())
total_revenue = float(daily["total_fare"].sum())
avg_fare = total_revenue / total_trips if total_trips else 0.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total trips", f"{total_trips:,}")
k2.metric("Total fares", f"{USD}{total_revenue:,.0f}")
k3.metric("Avg fare / trip", f"{USD}{avg_fare:,.2f}")
k4.metric("Days covered", f"{len(daily)}")

st.subheader("Daily revenue")
st.line_chart(daily.set_index("trip_date")["total_fare"])

st.subheader("Top pickup zones by revenue")
boroughs = ["All"] + sorted(zones["borough"].dropna().unique())
borough = st.selectbox("Borough", boroughs)
filtered = zones if borough == "All" else zones[zones["borough"] == borough]
top = (
    filtered.groupby("pickup_zone", as_index=False)
    .agg(trips=("trip_count", "sum"), revenue=("total_fare", "sum"))
    .sort_values("revenue", ascending=False)
    .head(10)
    .set_index("pickup_zone")
)
st.bar_chart(top["revenue"])

st.subheader("Last 14 days")
st.dataframe(
    daily.sort_values("trip_date", ascending=False).head(14),
    width="stretch",
)
