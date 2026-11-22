import json
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

from citytrips.pipeline import _build_geojson


def test_zone_export_normalizes_boundary_properties(tmp_path: Path) -> None:
    source_geojson = tmp_path / "taxi_zones.geojson"
    boundaries = gpd.GeoDataFrame(
        {
            "LocationID": [1],
            "Borough": ["Manhattan"],
            "Zone": ["Battery Park"],
        },
        geometry=[Polygon([(-74.02, 40.69), (-74, 40.69), (-74, 40.71), (-74.02, 40.69)])],
        crs="EPSG:4326",
    )
    boundaries.to_file(source_geojson, driver="GeoJSON")
    archive_path = tmp_path / "taxi_zones.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(source_geojson, arcname="taxi_zones.geojson")

    output_path = tmp_path / "public" / "taxi_zones.geojson"
    metadata = _build_geojson(archive_path, output_path)
    result = json.loads(output_path.read_text(encoding="utf-8"))

    assert metadata["features"] == 1
    assert result["features"][0]["properties"]["name"] == "1"
    assert result["features"][0]["properties"]["borough"] == "Manhattan"
    assert result["features"][0]["properties"]["zone"] == "Battery Park"


def test_zone_export_opens_shapefile_nested_in_source_archive(tmp_path: Path) -> None:
    shapefile_dir = tmp_path / "taxi_zones"
    shapefile_dir.mkdir()
    shapefile_path = shapefile_dir / "taxi_zones.shp"
    boundaries = gpd.GeoDataFrame(
        {
            "LocationID": [1],
            "borough": ["EWR"],
            "zone": ["Newark Airport"],
        },
        geometry=[Polygon([(-74.18, 40.68), (-74.16, 40.68), (-74.17, 40.70), (-74.18, 40.68)])],
        crs="EPSG:4326",
    )
    boundaries.to_file(shapefile_path, driver="ESRI Shapefile")
    archive_path = tmp_path / "taxi_zones.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for source_file in shapefile_dir.iterdir():
            archive.write(source_file, arcname=f"taxi_zones/{source_file.name}")

    output_path = tmp_path / "public" / "taxi_zones.geojson"
    _build_geojson(archive_path, output_path)
    result = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(result["features"]) == 1
    assert result["features"][0]["properties"]["borough"] == "EWR"
    assert result["features"][0]["properties"]["zone"] == "Newark Airport"
