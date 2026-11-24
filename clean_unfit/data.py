"""Acquire, verify and load the California Housing dataset (Pace & Barry, 1997).

The archive comes from the figshare mirror that scikit-learn uses and is verified
against a pinned SHA-256 before use. The data is not redistributed with this repo.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

SOURCE_URL = "https://ndownloader.figshare.com/files/5976036"
SOURCE_SHA256 = "aaa5c9a6afe2225cc2aed2723682ae403280c4a3695a2ddda4ffb5d8215ea681"
ARCHIVE_MEMBER = "CaliforniaHousing/cal_housing.data"
DOWNLOAD_TIMEOUT_SECONDS = 60

# Column order as documented in CaliforniaHousing/cal_housing.domain.
COLUMNS: tuple[str, ...] = (
    "longitude",
    "latitude",
    "housing_median_age",
    "total_rooms",
    "total_bedrooms",
    "population",
    "households",
    "median_income",
    "median_house_value",
)

FetchBytes = Callable[[str], bytes]

logger = logging.getLogger(__name__)


class DataAcquisitionError(RuntimeError):
    """The dataset could not be obtained or did not match its pinned checksum."""


@dataclass(frozen=True)
class Table:
    """Column-oriented numeric table. Rows that failed to parse are kept, not dropped."""

    columns: dict[str, list[float]]
    unparsed_rows: list[list[str]]

    @property
    def row_count(self) -> int:
        return len(next(iter(self.columns.values()))) if self.columns else 0


def fetch_url_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        return response.read()


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_archive(
    destination: Path,
    url: str = SOURCE_URL,
    expected_sha256: str = SOURCE_SHA256,
    fetch_bytes: FetchBytes = fetch_url_bytes,
) -> Path:
    """Download `url` to `destination` unless already present, then verify its checksum."""
    if not destination.exists():
        logger.info("downloading dataset", extra={"context": {"url": url, "destination": str(destination)}})
        try:
            payload = fetch_bytes(url)
        except OSError as error:
            raise DataAcquisitionError(f"download failed for {url}: {error}") from error
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary name first so an interrupted download never looks complete.
        partial_path = destination.with_suffix(destination.suffix + ".part")
        partial_path.write_bytes(payload)
        partial_path.replace(destination)

    actual_sha256 = compute_sha256(destination)
    if actual_sha256 != expected_sha256:
        raise DataAcquisitionError(
            f"checksum mismatch for {destination}: got {actual_sha256}, expected {expected_sha256}. "
            "Delete the file and retry, or check whether the upstream archive changed."
        )
    logger.info("dataset verified", extra={"context": {"path": str(destination), "sha256": actual_sha256}})
    return destination


def parse_rows(lines: Iterable[str], columns: tuple[str, ...] = COLUMNS) -> Table:
    """Parse comma-separated numeric rows; malformed rows go to `unparsed_rows`."""
    parsed_columns: dict[str, list[float]] = {name: [] for name in columns}
    unparsed_rows: list[list[str]] = []
    for raw_fields in csv.reader(lines):
        if not raw_fields:
            continue
        if len(raw_fields) != len(columns):
            unparsed_rows.append(raw_fields)
            continue
        try:
            values = [float(field) for field in raw_fields]
        except ValueError:
            unparsed_rows.append(raw_fields)
            continue
        for name, value in zip(columns, values):
            parsed_columns[name].append(value)
    return Table(columns=parsed_columns, unparsed_rows=unparsed_rows)


def load_table(archive_path: Path) -> Table:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.extractfile(ARCHIVE_MEMBER)
            if member is None:
                raise DataAcquisitionError(f"{ARCHIVE_MEMBER} is not a regular file in {archive_path}")
            table = parse_rows(io.TextIOWrapper(member, encoding="ascii"))
    except KeyError as error:
        raise DataAcquisitionError(f"{ARCHIVE_MEMBER} not found in {archive_path}") from error
    except tarfile.TarError as error:
        raise DataAcquisitionError(f"{archive_path} is not a readable .tar.gz archive: {error}") from error
    logger.info(
        "table loaded",
        extra={"context": {"rows": table.row_count, "unparsed_rows": len(table.unparsed_rows)}},
    )
    return table
