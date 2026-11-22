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
