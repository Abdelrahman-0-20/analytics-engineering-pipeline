"""Silver cleaning rules — pure functions so pytest can prove them."""
import pandas as pd


def clean_trips(df: pd.DataFrame, rules: dict) -> tuple[pd.DataFrame, dict]:
    # Fail early: refuse empty input instead of building an empty Silver layer.
    if df.empty:
        raise ValueError("Input is empty — refusing to build Silver from zero rows")

    # Fail loud: schema drift must be an error, never a silent column drop.
    required = rules.get("required_columns", [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Schema drift: missing required columns {missing}")

    out = df.copy()
    rejected: dict[str, int] = {}

    def step(name: str, mask) -> None:
        nonlocal out
        before = len(out)
        out = out[mask(out)]
        rejected[name] = before - len(out)

    # 1. no nulls in columns the star schema depends on
    step("null_values", lambda d: d[required].notna().all(axis=1))

    # 2. temporal sanity
    step("pickup_before_dropoff", lambda d: d["tpep_pickup_datetime"] < d["tpep_dropoff_datetime"])

    start = pd.Timestamp(rules["pickup_date"]["start"])
    end = pd.Timestamp(rules["pickup_date"]["end"])
    step("pickup_in_window", lambda d: (d["tpep_pickup_datetime"] >= start)
                                       & (d["tpep_pickup_datetime"] < end))

    def _duration(d: pd.DataFrame) -> pd.Series:
        minutes = (d["tpep_dropoff_datetime"] - d["tpep_pickup_datetime"]).dt.total_seconds() / 60
        lo = rules["duration_minutes"]["min"]
        hi = rules["duration_minutes"]["max"]
        return (minutes >= lo) & (minutes <= hi)

    step("duration_bounds", _duration)

    # 3. numeric ranges from config (negative fares, 500-mile trips, ...)
    def _range(col: str):
        def mask(d: pd.DataFrame) -> pd.Series:
            lo = rules[col]["min"]
            hi = rules[col]["max"]
            return (d[col] >= lo) & (d[col] <= hi)
        return mask

    for col in ("fare_amount", "trip_distance", "passenger_count", "payment_type"):
        step(f"{col}_in_range", _range(col))

    # 4. exact duplicate rows
    step("duplicates", lambda d: ~d.duplicated())

    report = {
        "input_rows": int(len(df)),
        "rejected": rejected,
        "rejected_total": int(sum(rejected.values())),
        "output_rows": int(len(out)),
    }
    if report["output_rows"] == 0:
        raise ValueError(f"All rows rejected — refusing to write empty Silver: {rejected}")
    return out.reset_index(drop=True), report
