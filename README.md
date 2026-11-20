# Trip Analytics Engineering Pipeline

A short, resume-focused ETL project: **public NYC TLC taxi data** (same schema family as
Uber fares — pickup/dropoff times, fares, tips, distances, NYC taxi zones) → cleaned
Bronze/Silver/Gold layers in **DuckDB** → proven by **pytest** → scheduled by
**GitHub Actions**. No API keys, no cloud accounts, no services to run.

## Architecture

```
data/raw/*.parquet  (immutable, fetched once, never modified)
        │  fetch.py — idempotent download
        ▼
bronze_trips        raw + _ingested_at + _source_file, append-once (ingest log)
        │  clean_trips() — nulls, date window, ranges, dedup  ← pytest covers this
        ▼
silver_trips        cleansed, deduplicated, conformable
dim_zones           zone dimension (borough / zone lookup)
        │  SQL aggregates
        ▼
gold_daily_revenue  revenue by day
gold_zone_daily     revenue by day × pickup zone
        │
        ▼
pipeline_log        every run recorded (rows in, rows out, rejected per rule)
```

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.pipeline   # fetch → bronze → silver → gold + sample queries
python -m pytest -q      # data quality gates must pass
```

Rerun either command any time — ingestion is idempotent (one ingest log entry per
source file) and Silver/Gold use `CREATE OR REPLACE`, so **running twice produces
the same warehouse, never duplicates**.

## Design decisions (interview talking points)

| Decision | Why |
|---|---|
| DuckDB over Snowflake/BigQuery | zero-ops, file-based, reproducible locally; same SQL/dbt skills transfer to any warehouse |
| Cleaning rules in `config.yaml` | thresholds are data, not code — tune without touching logic |
| Pure-function `clean_trips()` | testable without a database: DataFrame in → (DataFrame, report) out |
| Fail loud on schema drift / empty input | silent empty Silver is the classic pipeline failure |
| Append-once bronze via ingest log | replaying the pipeline cannot duplicate raw data |
| Half-open date window `[start, end)` | boundary dates are never double-counted or missed |

## Resume line

> Built an end-to-end ETL pipeline (Python/pandas/DuckDB) with layered Bronze→Silver→Gold
> transformations, pytest data-quality gates, idempotent ingestion, and daily scheduled
> runs via GitHub Actions.

## Stage B roadmap (later, not now)

- Streamlit dashboard reading the Gold layer
- dbt for the transformation layer
- H3/zone spatial analysis with GeoPandas
