from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _write_trips(path: Path, rows: list[dict[str, object]], *, include_fee: bool) -> None:
    columns = {
        "VendorID": pa.array([row["vendor_id"] for row in rows], type=pa.int64()),
        "tpep_pickup_datetime": pa.array([row["pickup"] for row in rows], type=pa.timestamp("us")),
        "tpep_dropoff_datetime": pa.array(
            [row["dropoff"] for row in rows], type=pa.timestamp("us")
        ),
        "PULocationID": pa.array([row["pickup_zone"] for row in rows], type=pa.int64()),
        "DOLocationID": pa.array([row["dropoff_zone"] for row in rows], type=pa.int64()),
        "passenger_count": pa.array([row["passengers"] for row in rows], type=pa.int64()),
        "trip_distance": pa.array([row["distance"] for row in rows], type=pa.float64()),
        "fare_amount": pa.array([row["fare"] for row in rows], type=pa.float64()),
        "tip_amount": pa.array([row["tip"] for row in rows], type=pa.float64()),
        "total_amount": pa.array([row["total"] for row in rows], type=pa.float64()),
    }
    if include_fee:
        columns["cbd_congestion_fee"] = pa.array([row["fee"] for row in rows], type=pa.float64())
    pq.write_table(pa.table(columns), path)


def _row(
    pickup: datetime,
    dropoff: datetime,
    *,
    distance: float = 1.5,
    pickup_zone: int = 1,
    dropoff_zone: int = 2,
    fee: float | None = None,
) -> dict[str, object]:
    return {
        "vendor_id": 1,
        "pickup": pickup,
        "dropoff": dropoff,
        "pickup_zone": pickup_zone,
        "dropoff_zone": dropoff_zone,
        "passengers": 1,
        "distance": distance,
        "fare": 12.0,
        "tip": 2.0,
        "total": 14.0,
        "fee": fee,
    }


def test_dbt_unifies_schema_reloads_months_and_reconciles_quality(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_trips(
        raw_dir / "yellow_tripdata_2024-01.parquet",
        [
            _row(datetime(2024, 1, 2, 8), datetime(2024, 1, 2, 8, 15)),
            _row(
                datetime(2024, 1, 2, 9),
                datetime(2024, 1, 2, 9, 30),
                pickup_zone=2,
                dropoff_zone=1,
            ),
            _row(datetime(2024, 2, 2, 9), datetime(2024, 2, 2, 9, 15)),
        ],
        include_fee=False,
    )
    _write_trips(
        raw_dir / "yellow_tripdata_2025-01.parquet",
        [
            _row(datetime(2025, 1, 5, 8), datetime(2025, 1, 5, 8, 20), fee=0.75),
            _row(datetime(2025, 1, 6, 9), datetime(2025, 1, 6, 9, 25), fee=1.5),
            _row(datetime(2025, 1, 6, 10), datetime(2025, 1, 6, 10, 25)),
            _row(datetime(2025, 1, 7, 10), datetime(2025, 1, 7, 10, 20), distance=-1, fee=None),
            _row(datetime(2025, 1, 8, 10), datetime(2025, 1, 8, 10, 20), pickup_zone=999, fee=None),
        ],
        include_fee=True,
    )
    zone_path = tmp_path / "taxi_zone_lookup.csv"
    with zone_path.open("w", newline="", encoding="utf-8") as zone_file:
        writer = csv.writer(zone_file)
        writer.writerow(["LocationID", "Borough", "Zone", "service_zone"])
        writer.writerow([1, "Manhattan", "Battery Park", "Yellow Zone"])
        writer.writerow([2, "Brooklyn", "DUMBO", "Boro Zone"])

    database_path = tmp_path / "citytrips.duckdb"
    variables = {
        "raw_glob": (raw_dir / "*.parquet").as_posix(),
        "zone_lookup_path": zone_path.as_posix(),
    }
    environment = {**os.environ, "DUCKDB_PATH": database_path.as_posix()}
    dbt_executable = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    assert dbt_executable.is_file(), "install project dependencies with `uv sync`"
    command = [
        str(dbt_executable),
        "build",
        "--project-dir",
        str(REPOSITORY_ROOT / "warehouse"),
        "--profiles-dir",
        str(REPOSITORY_ROOT / "warehouse"),
        "--vars",
        json.dumps(variables),
    ]

    first_build = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first_build.returncode == 0, first_build.stdout + first_build.stderr
    with duckdb.connect(database_path.as_posix(), read_only=True) as connection:
        monthly = connection.execute(
            "select month, trip_count, fee_reporting_status, "
            "reported_congestion_fee_total, fee_reporting_coverage "
            "from mart_monthly order by month"
        ).fetchall()
        quality = connection.execute(
            "select month, source_rows, accepted_rows, rejected_rows "
            "from mart_quality_monthly order by month"
        ).fetchall()

    assert monthly[0][0:3] == ("2024-01", 2, "not_available")
    assert monthly[0][3] is None
    assert monthly[0][4] == 0.0
    assert monthly[1][0:3] == ("2025-01", 3, "partially_reported")
    assert monthly[1][3] == 2.25
    assert monthly[1][4] == 0.6667
    assert quality == [("2024-01", 3, 2, 1), ("2025-01", 5, 3, 2)]

    second_build = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second_build.returncode == 0, second_build.stdout + second_build.stderr
    with duckdb.connect(database_path.as_posix(), read_only=True) as connection:
        counts = connection.execute(
            "select month, trip_count from mart_monthly order by month"
        ).fetchall()
    assert counts == [("2024-01", 2), ("2025-01", 3)]
