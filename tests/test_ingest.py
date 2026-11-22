import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from citytrips.ingest import (
    TripSource,
    discover_cloudfront_sources,
    download_trip_source,
    parse_trip_sources,
)


def test_parse_trip_sources_sorts_and_deduplicates_catalog_links() -> None:
    html = """
    <a href="https://data.example/yellow_tripdata_2025-03.parquet">March</a>
    <a href="https://data.example/yellow_tripdata_2023-12.parquet">Old</a>
    <a href="https://data.example/yellow_tripdata_2024-01.parquet">January</a>
    <a href="https://data.example/yellow_tripdata_2025-03.parquet">Duplicate</a>
    <a href="https://data.example/yellow_tripdata_2025-13.parquet">Invalid month</a>
    <a href="https://data.example/green_tripdata_2025-01.parquet">Other service</a>
    """

    sources = parse_trip_sources(html)

    assert [source.month for source in sources] == ["2024-01", "2025-03"]
    assert sources[1].url == "https://data.example/yellow_tripdata_2025-03.parquet"


def test_parse_trip_sources_respects_start_year() -> None:
    html = '<a href="https://data.example/yellow_tripdata_2025-01.parquet">January</a>'

    assert parse_trip_sources(html, start_year=2026) == []


def test_cloudfront_discovery_finds_latest_month_and_verifies_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    latest_month = "2025-03"

    def fake_metadata(url: str) -> dict[str, str | int | bool | None]:
        month = url.rsplit("_", maxsplit=1)[1].removesuffix(".parquet")
        return {"available": month <= latest_month, "etag": f'"{month}"'}

    monkeypatch.setattr("citytrips.ingest._remote_metadata", fake_metadata)

    sources = discover_cloudfront_sources(
        start_year=2025,
        today=datetime(2025, 5, 10, tzinfo=UTC),
    )

    assert [source.month for source in sources] == ["2025-01", "2025-02", "2025-03"]
    assert sources[-1].remote_metadata == {"available": True, "etag": '"2025-03"'}


def test_cloudfront_discovery_fails_on_gap_in_published_months(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_metadata(url: str) -> dict[str, str | int | bool | None]:
        month = url.rsplit("_", maxsplit=1)[1].removesuffix(".parquet")
        return {"available": month != "2025-02"}

    monkeypatch.setattr("citytrips.ingest._remote_metadata", fake_metadata)

    with pytest.raises(RuntimeError, match="2025-02 is missing"):
        discover_cloudfront_sources(start_year=2025, today=datetime(2025, 3, 10, tzinfo=UTC))


def test_download_trip_source_records_parquet_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    parquet_path = tmp_path / "source.parquet"
    table = pa.table({"VendorID": [1, 2], "trip_distance": [1.2, 3.4]})
    pq.write_table(table, parquet_path)

    def fake_download(url: str, destination: Path) -> str:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(parquet_path.read_bytes())
        return "a" * 64

    monkeypatch.setattr("citytrips.ingest._remote_metadata", lambda url: {})
    monkeypatch.setattr("citytrips.ingest.download_file", fake_download)
    record = download_trip_source(
        TripSource(month="2024-01", url="https://data.example/yellow_tripdata_2024-01.parquet"),
        tmp_path / "raw",
    )

    assert record.month == "2024-01"
    assert record.rows == 2
    assert record.columns == ["VendorID", "trip_distance"]
    assert record.sha256 == "a" * 64


def test_download_trip_source_reuses_cached_file_only_for_matching_validators(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    source = TripSource(
        month="2024-01",
        url="https://data.example/yellow_tripdata_2024-01.parquet",
    )
    path = raw_dir / "yellow_tripdata_2024-01.parquet"
    pq.write_table(pa.table({"VendorID": [1], "trip_distance": [1.2]}), path)
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    remote = {
        "etag": '"revision-1"',
        "last_modified": "Wed, 01 Jan 2025 00:00:00 GMT",
        "size_bytes": path.stat().st_size,
    }
    previous = {
        "url": source.url,
        "sha256": checksum,
        "etag": remote["etag"],
        "last_modified": remote["last_modified"],
        "size_bytes": remote["size_bytes"],
    }
    monkeypatch.setattr("citytrips.ingest._remote_metadata", lambda url: remote)
    monkeypatch.setattr(
        "citytrips.ingest.download_file",
        lambda *args, **kwargs: pytest.fail("unchanged source should reuse the verified cache"),
    )

    record = download_trip_source(source, raw_dir, previous)

    assert record.sha256 == checksum
    assert record.rows == 1
    assert record.etag == '"revision-1"'
