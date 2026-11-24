"""Shared test fixtures: small in-memory tables and archives with known properties."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from clean_unfit.data import ARCHIVE_MEMBER, COLUMNS, Table

# A valid row: Bay Area coordinates, plausible counts, income 8.3 ($83k), value $452,600.
VALID_ROW = (-122.23, 37.88, 41.0, 880.0, 129.0, 322.0, 126.0, 8.3252, 452_600.0)


def make_table(rows: list[tuple[float, ...]], unparsed_rows: list[list[str]] | None = None) -> Table:
    columns = {name: [row[index] for row in rows] for index, name in enumerate(COLUMNS)}
    return Table(columns=columns, unparsed_rows=unparsed_rows or [])


def vary_row(row_index: int, house_value: float, income: float) -> tuple[float, ...]:
    """A valid, unique row with the given house value and income."""
    longitude, latitude, age, rooms, bedrooms, population, households, _, _ = VALID_ROW
    return (longitude, latitude, age, rooms + row_index, bedrooms, population, households, income, house_value)


def write_archive(path: Path, csv_text: str, member_name: str = ARCHIVE_MEMBER) -> Path:
    payload = csv_text.encode("ascii")
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(member_name)
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return path
