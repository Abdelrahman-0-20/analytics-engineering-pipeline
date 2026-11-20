"""Export Gold tables to CSV snapshots consumed by the Streamlit dashboard.

Run after the pipeline: python -m src.export_gold
"""
from pathlib import Path

from . import load as etl
from .config import load_config, ROOT

OUT_DIR = ROOT / "dashboard" / "data"
TABLES = ("gold_daily_revenue", "gold_zone_daily")


def main() -> None:
    cfg = load_config()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = etl.connect(cfg)
    try:
        for table in TABLES:
            df = con.execute(f"SELECT * FROM {table}").df()
            if df.empty:
                raise RuntimeError(f"{table} is empty — run the pipeline first")
            path = OUT_DIR / f"{table}.csv"
            df.to_csv(path, index=False)
            print(f"[export] {table}: {len(df):,} rows -> {path.relative_to(ROOT)}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
