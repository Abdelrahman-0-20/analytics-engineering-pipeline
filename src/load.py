"""Bronze -> Silver -> Gold into DuckDB. Every step idempotent: rerun = same result."""
import json
from datetime import datetime

import duckdb

from .clean import clean_trips
from .config import resolve


def connect(cfg: dict) -> duckdb.DuckDBPyConnection:
    db_path = resolve(cfg["paths"]["warehouse"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def ingest_bronze(cfg: dict, con) -> int:
    """Append raw trips to Bronze exactly once per source file."""
    src = resolve(cfg["source"]["trips"]["file"])
    if not src.exists():
        raise FileNotFoundError(f"Raw file missing: {src} — run fetch first")

    con.execute("""
        CREATE TABLE IF NOT EXISTS _ingest_log (
            source_file VARCHAR PRIMARY KEY,
            ingested_at TIMESTAMP,
            row_count BIGINT
        )
    """)
    if con.execute("SELECT 1 FROM _ingest_log WHERE source_file = ?", [src.name]).fetchone():
        print(f"[bronze] {src.name} already ingested — skipped (idempotent)")
        return 0

    exists = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'bronze_trips'"
    ).fetchone()[0] > 0
    before = con.execute("SELECT COUNT(*) FROM bronze_trips").fetchone()[0] if exists else 0

    con.execute("BEGIN TRANSACTION")
    try:
        sql = ("CREATE TABLE bronze_trips AS" if not exists
               else "INSERT INTO bronze_trips")
        select = """
            SELECT *, now() AS _ingested_at, ? AS _source_file
            FROM read_parquet(?)
        """
        con.execute(f"{sql} {select}" if not exists else f"{sql} {select}",
                    [src.name, str(src)])
        after = con.execute("SELECT COUNT(*) FROM bronze_trips").fetchone()[0]
        con.execute("INSERT INTO _ingest_log VALUES (?, ?, ?)",
                    [src.name, datetime.now(), after - before])
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise

    rows = after - before
    print(f"[bronze] ingested {rows:,} raw rows")
    return rows


def build_silver(cfg: dict, con) -> dict:
    """Cleanse Bronze -> Silver. CREATE OR REPLACE makes reruns idempotent."""
    bronze = con.execute("SELECT * FROM bronze_trips").df()
    silver, report = clean_trips(bronze, cfg["cleaning"])
    con.register("silver_src", silver)
    con.execute("CREATE OR REPLACE TABLE silver_trips AS SELECT * FROM silver_src")
    con.unregister("silver_src")
    print(f"[silver] {report['input_rows']:,} -> {report['output_rows']:,} rows "
          f"({report['rejected_total']:,} rejected)")
    return report


def load_dim_zones(cfg: dict, con) -> int:
    src = resolve(cfg["source"]["zones"]["file"])
    if not src.exists():
        raise FileNotFoundError(f"Zone lookup missing: {src} — run fetch first")
    con.execute("CREATE OR REPLACE TABLE dim_zones AS SELECT * FROM read_csv(?)",
                [str(src)])
    n = con.execute("SELECT COUNT(*) FROM dim_zones").fetchone()[0]
    print(f"[dim] dim_zones: {n} rows")
    return n


def build_gold(con) -> None:
    """Business aggregates. CREATE OR REPLACE = rerun safe, no duplicate rows."""
    con.execute("""
        CREATE OR REPLACE TABLE gold_daily_revenue AS
        SELECT CAST(tpep_pickup_datetime AS DATE) AS trip_date,
               COUNT(*) AS trip_count,
               ROUND(SUM(fare_amount), 2) AS total_fare,
               ROUND(SUM(tip_amount), 2) AS total_tip,
               ROUND(AVG(trip_distance), 2) AS avg_distance,
               CURRENT_TIMESTAMP AS refreshed_at
        FROM silver_trips
        GROUP BY 1
        ORDER BY 1
    """)
    con.execute("""
        CREATE OR REPLACE TABLE gold_zone_daily AS
        SELECT CAST(s.tpep_pickup_datetime AS DATE) AS trip_date,
               z."Borough" AS borough,
               z."Zone" AS pickup_zone,
               COUNT(*) AS trip_count,
               ROUND(SUM(s.fare_amount), 2) AS total_fare,
               CURRENT_TIMESTAMP AS refreshed_at
        FROM silver_trips s
        JOIN dim_zones z ON s.PULocationID = z."LocationID"
        GROUP BY 1, 2, 3
    """)
    daily = con.execute("SELECT COUNT(*) FROM gold_daily_revenue").fetchone()[0]
    zones = con.execute("SELECT COUNT(*) FROM gold_zone_daily").fetchone()[0]
    print(f"[gold] gold_daily_revenue: {daily} rows | gold_zone_daily: {zones} rows")


def log_run(con, step_name: str, report: dict) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_log (
            ran_at TIMESTAMP,
            step VARCHAR,
            input_rows BIGINT,
            output_rows BIGINT,
            rejected BIGINT,
            detail VARCHAR
        )
    """)
    con.execute("INSERT INTO pipeline_log VALUES (now(), ?, ?, ?, ?, ?)", [
        step_name,
        report.get("input_rows"),
        report.get("output_rows"),
        report.get("rejected_total"),
        json.dumps(report.get("rejected", {})),
    ])
