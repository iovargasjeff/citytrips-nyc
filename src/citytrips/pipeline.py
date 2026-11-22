"""Command line entry point for a complete public data refresh."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import geopandas as gpd

from citytrips.ingest import refresh_sources


def _run_dbt(repository_root: Path, data_root: Path, database_path: Path) -> None:
    warehouse_dir = repository_root / "warehouse"
    variables = {
        "raw_glob": (data_root / "raw" / "*.parquet").as_posix(),
        "zone_lookup_path": (data_root / "taxi_zone_lookup.csv").as_posix(),
    }
    environment = os.environ.copy()
    environment["DUCKDB_PATH"] = database_path.as_posix()
    dbt_executable = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    if not dbt_executable.is_file():
        located_executable = shutil.which("dbt", path=environment.get("PATH"))
        if located_executable is None:
            raise RuntimeError(
                "dbt executable not found; install project dependencies with `uv sync`"
            )
        dbt_executable = Path(located_executable)
    subprocess.run(
        [
            str(dbt_executable),
            "build",
            "--project-dir",
            str(warehouse_dir),
            "--profiles-dir",
            str(warehouse_dir),
            "--vars",
            json.dumps(variables),
        ],
        cwd=repository_root,
        env=environment,
        check=True,
    )


def _export_relation(connection: duckdb.DuckDBPyConnection, relation: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    escaped_path = str(path.resolve()).replace("'", "''")
    connection.execute(
        f"COPY (SELECT * FROM {relation}) TO '{escaped_path}' (FORMAT JSON, ARRAY true)"
    )


def _build_geojson(archive_path: Path, output_path: Path) -> dict[str, int]:
    if not zipfile.is_zipfile(archive_path):
        raise ValueError(f"Taxi zone boundary archive is not a ZIP file: {archive_path}")

    with zipfile.ZipFile(archive_path) as archive:
        vector_files = [
            name
            for name in archive.namelist()
            if Path(name).suffix.casefold() in {".shp", ".geojson", ".json"}
        ]
    shapefiles = [name for name in vector_files if Path(name).suffix.casefold() == ".shp"]
    data_sources = shapefiles or vector_files
    if len(data_sources) != 1:
        raise ValueError(
            f"Expected one taxi zone shapefile or GeoJSON in {archive_path}, "
            f"found {len(data_sources)}"
        )

    zones = gpd.read_file(f"zip://{archive_path.resolve().as_posix()}!{data_sources[0]}")
    if "LocationID" not in zones.columns:
        raise ValueError("Taxi zone boundaries do not include LocationID")

    column_by_name = {column.casefold(): column for column in zones.columns}
    for normalized_name in ("borough", "zone"):
        source_name = column_by_name.get(normalized_name)
        if source_name is None:
            raise ValueError(f"Taxi zone boundaries do not include {normalized_name}")
        if source_name != normalized_name:
            zones = zones.rename(columns={source_name: normalized_name})

    zones = zones.to_crs("EPSG:4326")
    zones["geometry"] = zones.geometry.simplify(0.00012, preserve_topology=True)
    zones["name"] = zones["LocationID"].astype(str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(zones.to_json(drop_id=True), encoding="utf-8")
    return {"features": len(zones), "bytes": output_path.stat().st_size}


def build_public_data(repository_root: Path, data_root: Path, output_dir: Path) -> dict[str, Any]:
    database_path = data_root / "citytrips.duckdb"
    _run_dbt(repository_root, data_root, database_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(database_path.as_posix(), read_only=True) as connection:
        _export_relation(connection, "mart_monthly", output_dir / "monthly.json")
        _export_relation(connection, "mart_month_hour", output_dir / "monthly_hour.json")
        _export_relation(connection, "mart_zone_month", output_dir / "zone_month.json")
        _export_relation(connection, "mart_quality_monthly", output_dir / "quality.json")
        quality_cursor = connection.execute("SELECT * FROM mart_quality_monthly")
        quality_columns = [column[0] for column in quality_cursor.description]
        quality_rows = [
            dict(zip(quality_columns, row, strict=True)) for row in quality_cursor.fetchall()
        ]

    source_manifest = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    boundary_metadata = _build_geojson(
        data_root / "taxi_zones.zip", output_dir / "taxi_zones.geojson"
    )
    public_manifest = {
        "schema_version": 1,
        "dataset_type": "published",
        "built_at": source_manifest["built_at"],
        "latest_month": source_manifest["source_months"][-1],
        "source_month_count": len(source_manifest["source_months"]),
        "source_file_count": len(source_manifest["files"]),
        "source_total_rows": sum(file_record["rows"] for file_record in source_manifest["files"]),
        "published_months": source_manifest["source_months"],
        "files": source_manifest["files"],
        "quality": quality_rows,
        "taxi_zone_boundaries": boundary_metadata,
        "source": {
            "name": "NYC Taxi and Limousine Commission Yellow Taxi Trip Records",
            "url": source_manifest["catalog_url"],
            "zone_lookup_sha256": source_manifest["zone_lookup"]["sha256"],
            "zone_boundaries_sha256": source_manifest["zone_boundaries"]["sha256"],
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(public_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return public_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the CityTrips NYC data products.")
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--output", type=Path, default=Path("web/public/data"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="redownload every published Parquet file instead of reusing verified cache entries",
    )
    args = parser.parse_args()

    repository_root = args.repository_root.resolve()
    data_root = args.data_dir.resolve()
    output_dir = args.output.resolve()
    refresh_sources(
        output_dir=data_root,
        start_year=args.start_year,
        force_download=args.force_download,
    )
    manifest = build_public_data(repository_root, data_root, output_dir)
    print(
        f"Published {manifest['source_month_count']} months and "
        f"{manifest['source_total_rows']:,} source rows through {manifest['latest_month']}"
    )


if __name__ == "__main__":
    main()
