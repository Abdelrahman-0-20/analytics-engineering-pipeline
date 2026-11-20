"""Prove Bronze ingestion is idempotent: run twice, same rows."""
import pandas as pd

from src import load as etl


def _cfg(tmp_path) -> dict:
    return {
        "source": {"trips": {"file": str(tmp_path / "sample.parquet")}},
        "paths": {"warehouse": str(tmp_path / "warehouse.duckdb")},
    }


def test_bronze_ingest_is_idempotent(tmp_path):
    parquet = tmp_path / "sample.parquet"
    pd.DataFrame({
        "tpep_pickup_datetime": [pd.Timestamp("2024-01-15 10:00:00")] * 2,
        "fare_amount": [14.5, 8.0],
    }).to_parquet(parquet)

    cfg = _cfg(tmp_path)
    con = etl.connect(cfg)
    try:
        first = etl.ingest_bronze(cfg, con)
        second = etl.ingest_bronze(cfg, con)  # rerun must not duplicate

        assert first == 2
        assert second == 0
        assert con.execute("SELECT COUNT(*) FROM bronze_trips").fetchone()[0] == 2
    finally:
        con.close()
