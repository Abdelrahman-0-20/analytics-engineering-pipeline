"""Prove the cleaner rejects bad rows and keeps good ones."""
import pandas as pd
import pytest

from src.clean import clean_trips

RULES = {
    "required_columns": [
        "tpep_pickup_datetime", "tpep_dropoff_datetime",
        "passenger_count", "trip_distance", "fare_amount",
        "tip_amount", "payment_type", "PULocationID", "DOLocationID",
    ],
    "pickup_date": {"start": "2024-01-01", "end": "2024-02-01"},
    "duration_minutes": {"min": 1, "max": 1440},
    "fare_amount": {"min": 0.0, "max": 300.0},
    "trip_distance": {"min": 0.0, "max": 100.0},
    "passenger_count": {"min": 1, "max": 9},
    "payment_type": {"min": 1, "max": 6},
}


def _row(**overrides) -> dict:
    base = {
        "tpep_pickup_datetime": pd.Timestamp("2024-01-15 10:00:00"),
        "tpep_dropoff_datetime": pd.Timestamp("2024-01-15 10:20:00"),
        "passenger_count": 1.0,
        "trip_distance": 3.5,
        "fare_amount": 14.5,
        "tip_amount": 3.0,
        "payment_type": 1,
        "PULocationID": 161,
        "DOLocationID": 236,
    }
    base.update(overrides)
    return base


def test_keeps_only_valid_rows():
    df = pd.DataFrame([
        _row(),                                                       # good
        _row(fare_amount=-5.0),                                       # negative fare
        _row(trip_distance=500.0),                                    # absurd distance
        _row(tpep_pickup_datetime=pd.Timestamp("2023-12-31 23:00:00"),
             tpep_dropoff_datetime=pd.Timestamp("2024-01-01 01:00:00")),  # outside window
        _row(tpep_pickup_datetime=pd.Timestamp("2024-01-15 11:00:00"),
             tpep_dropoff_datetime=pd.Timestamp("2024-01-15 10:00:00")),  # dropoff earlier
        _row(passenger_count=None),                                   # null
        _row(payment_type=99),                                        # out of domain
    ])
    out, report = clean_trips(df, RULES)
    assert len(out) == 1
    assert report["rejected_total"] == 6
    assert report["rejected"]["fare_amount_in_range"] == 1
    assert report["rejected"]["null_values"] == 1


def test_duplicate_rows_are_dropped():
    df = pd.DataFrame([_row(), _row()])
    out, report = clean_trips(df, RULES)
    assert len(out) == 1
    assert report["rejected"]["duplicates"] == 1


def test_schema_drift_fails_loud():
    df = pd.DataFrame([_row()]).drop(columns=["fare_amount"])
    with pytest.raises(KeyError, match="fare_amount"):
        clean_trips(df, RULES)


def test_empty_input_fails_loud():
    with pytest.raises(ValueError, match="empty"):
        clean_trips(pd.DataFrame([]), RULES)
