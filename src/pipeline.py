"""Run the full pipeline: python -m src.pipeline"""
from . import load as etl
from .config import load_config
from .fetch import fetch


def main() -> None:
    cfg = load_config()
    print("=== Trip ETL pipeline ===")
    fetch(cfg)                                     # raw files (skipped if present)
    con = etl.connect(cfg)
    try:
        etl.ingest_bronze(cfg, con)                # raw -> bronze (once per file)
        silver_report = etl.build_silver(cfg, con)  # bronze -> silver (clean)
        etl.load_dim_zones(cfg, con)               # zone dimension
        etl.build_gold(con)                        # silver -> gold (aggregates)
        etl.log_run(con, "bronze_to_silver", silver_report)

        print("\nTop 5 revenue days:")
        for row in con.execute("""
            SELECT trip_date, trip_count, total_fare, total_tip
            FROM gold_daily_revenue ORDER BY total_fare DESC LIMIT 5
        """).fetchall():
            print("  ", row)

        print("\nTop 5 pickup zones:")
        for row in con.execute("""
            SELECT pickup_zone, SUM(trip_count) AS trips, ROUND(SUM(total_fare), 2) AS fare
            FROM gold_zone_daily GROUP BY 1 ORDER BY fare DESC LIMIT 5
        """).fetchall():
            print("  ", row)
    finally:
        con.close()
    print("\nDone. Warehouse: warehouse/trips.duckdb")


if __name__ == "__main__":
    main()
