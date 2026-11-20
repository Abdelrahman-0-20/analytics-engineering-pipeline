# Trip Analytics Engineering Pipeline

[![ETL pipeline](https://github.com/Abdelrahman-0-20/analytics-engineering-pipeline/actions/workflows/pipeline.yml/badge.svg)](https://github.com/Abdelrahman-0-20/analytics-engineering-pipeline/actions/workflows/pipeline.yml)

Project #1 of a [data engineering portfolio](https://github.com/Abdelrahman-0-20/api-ingestion-pipeline)
(companion: [API ingestion pipeline](https://github.com/Abdelrahman-0-20/api-ingestion-pipeline) — live-source ingestion).

A short, resume-focused ETL project: **public NYC TLC taxi data** (same schema family as
Uber fares — pickup/dropoff times, fares, tips, distances, NYC taxi zones) → cleaned
Bronze/Silver/Gold layers in **DuckDB** → proven by **pytest** → scheduled by
**GitHub Actions**. No API keys, no cloud accounts, no services to run.

**Pipeline at a glance:** 2.96M raw rows ingested · 235,582 rejected by quality
gates (7.9%) · 31 days of revenue · 6,689 zone-day aggregates · rerun-safe
(proven idempotent: second run changes nothing).

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

python -m src.pipeline      # fetch → bronze → silver → gold + sample queries
python -m src.export_gold   # export Gold tables to dashboard/data/*.csv
python -m pytest -q         # data quality gates must pass
streamlit run app.py        # dashboard on the Gold layer
```

## Dashboard

`app.py` is a Streamlit app serving the **Gold layer only** (never Bronze/Silver).
CI exports `dashboard/data/*.csv` after every pipeline run and commits them back
(`[skip ci]`), so the deployed app always shows fresh numbers without needing
database access. Deploy free on [Streamlit Community Cloud](https://share.streamlit.io)
by connecting this repo — it runs `streamlit run app.py` automatically.

Re-running is safe: ingestion is logged once per source file and Silver/Gold use
`CREATE OR REPLACE`, so **running twice produces the same warehouse, never
duplicates** — verified by tests.

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

## Ideas for later

- dbt for the transformation layer
- H3/zone spatial analysis with GeoPandas
- Alerting when a quality gate fails (email/Slack webhook)
