"""Download and validate monthly source files from the NYC TLC data page."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pyarrow.parquet as pq
import requests
from bs4 import BeautifulSoup

TLC_PAGE_URL = "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page"
TAXI_ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
TAXI_ZONES_ARCHIVE_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip"
TAXI_TRIP_DATA_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
TRIP_FILE_PATTERN = re.compile(r"yellow_tripdata_(\d{4})-(\d{2})\.parquet$", re.IGNORECASE)


@dataclass(frozen=True)
class TripSource:
    month: str
    url: str
    remote_metadata: dict[str, str | int | bool | None] | None = None


@dataclass(frozen=True)
class DownloadRecord:
    month: str
    url: str
    path: str
    sha256: str
    rows: int
    columns: list[str]
    etag: str | None
    last_modified: str | None
    size_bytes: int


def parse_trip_sources(html: str, start_year: int = 2024) -> list[TripSource]:
    """Find published yellow taxi Parquet links from the TLC catalog HTML."""
    soup = BeautifulSoup(html, "html.parser")
    sources: dict[str, TripSource] = {}

    for anchor in soup.find_all("a", href=True):
        url = anchor["href"].strip()
        filename = Path(urlparse(url).path).name
        match = TRIP_FILE_PATTERN.fullmatch(filename)
        if match is None:
            continue

        year, month_number = map(int, match.groups())
        if year < start_year or not 1 <= month_number <= 12:
            continue

        month = f"{year:04d}-{month_number:02d}"
        sources[month] = TripSource(month=month, url=url)

    return [sources[month] for month in sorted(sources)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remote_metadata(url: str) -> dict[str, str | int | bool | None]:
    """Read HTTP validators to reuse unchanged source files from a restored cache."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=(15, 60))
        if response.status_code in {403, 405, 410, 501}:
            return {"available": None}
        if response.status_code == 404:
            return {"available": False}
        response.raise_for_status()
    except requests.RequestException:
        return {"available": None}

    content_length = response.headers.get("Content-Length")
    return {
        "available": True,
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "size_bytes": int(content_length)
        if content_length and content_length.isdecimal()
        else None,
    }


def discover_cloudfront_sources(
    start_year: int = 2024,
    *,
    today: datetime | None = None,
) -> list[TripSource]:
    """Find TLC's newest published month, then verify every intervening source month."""
    current = today or datetime.now(UTC)
    candidate_year, candidate_month = current.year, current.month
    latest_month: str | None = None
    latest_metadata: dict[str, str | int | bool | None] | None = None

    for _ in range(12):
        month = f"{candidate_year:04d}-{candidate_month:02d}"
        url = f"{TAXI_TRIP_DATA_BASE_URL}/yellow_tripdata_{month}.parquet"
        metadata = _remote_metadata(url)
        if metadata.get("available") is True:
            latest_month = month
            latest_metadata = metadata
            break
        candidate_month -= 1
        if candidate_month == 0:
            candidate_year -= 1
            candidate_month = 12

    if latest_month is None or latest_metadata is None:
        raise RuntimeError("Could not locate a published TLC yellow taxi month on CloudFront")
    if int(latest_month[:4]) < start_year:
        return []

    year, month_number = start_year, 1
    months: list[str] = []
    while f"{year:04d}-{month_number:02d}" <= latest_month:
        months.append(f"{year:04d}-{month_number:02d}")
        month_number += 1
        if month_number == 13:
            year += 1
            month_number = 1

    sources: list[TripSource] = []
    for month in months:
        url = f"{TAXI_TRIP_DATA_BASE_URL}/yellow_tripdata_{month}.parquet"
        metadata = latest_metadata if month == latest_month else _remote_metadata(url)
        if metadata.get("available") is False:
            raise RuntimeError(f"TLC source month {month} is missing before {latest_month}")
        sources.append(TripSource(month=month, url=url, remote_metadata=metadata))

    return sources


def _download_to_path(url: str, destination: Path, timeout: tuple[int, int]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f"{destination.name}.",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            with requests.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        temporary_file.write(chunk)

        if destination.suffix.lower() == ".parquet":
            pq.read_metadata(temporary_path)
        elif destination.suffix.lower() == ".zip" and not zipfile.is_zipfile(temporary_path):
            raise ValueError(f"Downloaded file is not a valid ZIP archive: {url}")

        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def download_file(
    url: str,
    destination: Path,
    *,
    retries: int = 3,
    timeout: tuple[int, int] = (15, 300),
) -> str:
    """Download a file atomically with bounded retries and return its checksum."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            _download_to_path(url, destination, timeout)
            return _sha256(destination)
        except (requests.RequestException, OSError, ValueError) as error:
            last_error = error
            if attempt + 1 == retries:
                break

    raise RuntimeError(f"Failed to download {url} after {retries} attempts") from last_error


def download_trip_source(
    source: TripSource,
    raw_dir: Path,
    previous_record: dict[str, Any] | None = None,
) -> DownloadRecord:
    path = raw_dir / f"yellow_tripdata_{source.month}.parquet"
    remote = source.remote_metadata or _remote_metadata(source.url)
    validators = ("etag", "last_modified", "size_bytes")
    comparable_validators = [
        key
        for key in validators
        if remote.get(key) is not None and previous_record and previous_record.get(key) is not None
    ]
    same_source_version = bool(comparable_validators) and all(
        remote[key] == previous_record[key] for key in comparable_validators
    )
    checksum = None
    if (
        previous_record
        and previous_record.get("url") == source.url
        and same_source_version
        and path.is_file()
    ):
        cached_checksum = _sha256(path)
        if cached_checksum == previous_record.get("sha256"):
            checksum = cached_checksum
    if checksum is None:
        checksum = download_file(source.url, path)

    metadata = pq.read_metadata(path)
    schema = pq.read_schema(path)
    return DownloadRecord(
        month=source.month,
        url=source.url,
        path=path.as_posix(),
        sha256=checksum,
        rows=metadata.num_rows,
        columns=schema.names,
        etag=remote.get("etag"),
        last_modified=remote.get("last_modified"),
        size_bytes=path.stat().st_size,
    )


def _write_json_atomically(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".part")
    temporary_path.write_text(
        json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary_path, path)


def refresh_sources(
    *,
    output_dir: Path,
    start_year: int = 2024,
    page_url: str = TLC_PAGE_URL,
    workers: int = 4,
    force_download: bool = False,
) -> dict[str, Any]:
    """Fetch the published source window and record a complete, checksum-based manifest."""
    discovery_method = "tlc_catalog_page"
    try:
        response = requests.get(page_url, timeout=(15, 60))
        response.raise_for_status()
        sources = parse_trip_sources(response.text, start_year=start_year)
    except requests.RequestException as error:
        print(f"TLC catalog page unavailable ({error}); probing its public CloudFront files.")
        sources = []

    if not sources:
        sources = discover_cloudfront_sources(start_year=start_year)
        discovery_method = "cloudfront_head_probe"
    if not sources:
        raise RuntimeError(f"No yellow taxi Parquet files from {start_year} onward were found")

    raw_dir = output_dir / "raw"
    previous_files: dict[str, dict[str, Any]] = {}
    previous_manifest_path = output_dir / "manifest.json"
    if not force_download and previous_manifest_path.is_file():
        try:
            previous_manifest = json.loads(previous_manifest_path.read_text(encoding="utf-8"))
            previous_files = {
                record["month"]: record for record in previous_manifest.get("files", [])
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            previous_files = {}

    records: list[DownloadRecord] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        pending = {
            executor.submit(
                download_trip_source,
                source,
                raw_dir,
                previous_files.get(source.month),
            ): source
            for source in sources
        }
        for future in as_completed(pending):
            records.append(future.result())

    current_paths = {
        (raw_dir / f"yellow_tripdata_{source.month}.parquet").resolve() for source in sources
    }
    for cached_path in raw_dir.glob("yellow_tripdata_????-??.parquet"):
        if cached_path.resolve() not in current_paths:
            cached_path.unlink()

    zone_lookup = output_dir / "taxi_zone_lookup.csv"
    zone_checksum = download_file(TAXI_ZONE_LOOKUP_URL, zone_lookup)
    zones_archive = output_dir / "taxi_zones.zip"
    boundaries_checksum = download_file(TAXI_ZONES_ARCHIVE_URL, zones_archive)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "built_at": datetime.now(UTC).isoformat(),
        "catalog_url": page_url,
        "discovery_method": discovery_method,
        "start_year": start_year,
        "source_months": sorted(record.month for record in records),
        "files": [asdict(record) for record in sorted(records, key=lambda record: record.month)],
        "zone_lookup": {
            "url": TAXI_ZONE_LOOKUP_URL,
            "path": zone_lookup.as_posix(),
            "sha256": zone_checksum,
        },
        "zone_boundaries": {
            "url": TAXI_ZONES_ARCHIVE_URL,
            "path": zones_archive.as_posix(),
            "sha256": boundaries_checksum,
        },
    }
    _write_json_atomically(output_dir / "manifest.json", manifest)
    return manifest
