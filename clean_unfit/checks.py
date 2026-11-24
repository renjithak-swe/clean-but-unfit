"""Data-quality checks.

`run_generic_suite` is deliberately question-agnostic. It encodes the rules a typical
pipeline validates: schema, parsing, completeness, uniqueness, ranges and cross-field
consistency. `measure_boundary_mass` is a distribution check for values piled up at a
column's minimum or maximum, which is a common signature of top- or bottom-coding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .data import COLUMNS, Table

# Approximate bounding box of California, used as a validity range.
CALIFORNIA_LONGITUDE_RANGE = (-124.5, -114.1)
CALIFORNIA_LATITUDE_RANGE = (32.5, 42.1)
POSITIVE_COLUMNS = COLUMNS[2:]
DEFAULT_BOUNDARY_SHARE_THRESHOLD = 0.005


@dataclass(frozen=True)
class CheckResult:
    name: str
    is_passed: bool
    failing_rows: int
    total_rows: int


@dataclass(frozen=True)
class BoundaryMass:
    column: str
    side: str
    value: float
    row_count: int
    share: float
    is_flagged: bool


def _count_outside(values: list[float], bounds: tuple[float, float]) -> int:
    lower, upper = bounds
    return sum(1 for value in values if not lower <= value <= upper)


def run_generic_suite(table: Table) -> list[CheckResult]:
    columns = table.columns
    total_rows = table.row_count
    missing_columns = [name for name in COLUMNS if name not in columns]
    if missing_columns:
        return [CheckResult(f"schema: missing columns {missing_columns}", False, total_rows, total_rows)]

    def make_result(name: str, failing_rows: int, denominator: int = total_rows) -> CheckResult:
        return CheckResult(name, failing_rows == 0, failing_rows, denominator)

    all_rows = list(zip(*(columns[name] for name in COLUMNS)))
    results = [
        make_result("schema: expected columns present", 0),
        make_result(
            "parse: every row has 9 numeric fields",
            len(table.unparsed_rows),
            total_rows + len(table.unparsed_rows),
        ),
        make_result(
            "completeness: no NaN or infinite values",
            sum(1 for row in all_rows if not all(math.isfinite(value) for value in row)),
        ),
        make_result("uniqueness: no duplicate rows", total_rows - len(set(all_rows))),
        make_result(
            "range: longitude within California",
            _count_outside(columns["longitude"], CALIFORNIA_LONGITUDE_RANGE),
        ),
        make_result(
            "range: latitude within California",
            _count_outside(columns["latitude"], CALIFORNIA_LATITUDE_RANGE),
        ),
    ]
    results += [
        make_result(f"range: {name} > 0", sum(1 for value in columns[name] if value <= 0))
        for name in POSITIVE_COLUMNS
    ]
    results += [
        make_result(
            "consistency: total_bedrooms <= total_rooms",
            sum(1 for bedrooms, rooms in zip(columns["total_bedrooms"], columns["total_rooms"]) if bedrooms > rooms),
        ),
        make_result(
            "consistency: households <= population",
            sum(1 for households, people in zip(columns["households"], columns["population"]) if households > people),
        ),
    ]
    return results


def measure_boundary_mass(
    values: list[float],
    column: str,
    threshold: float = DEFAULT_BOUNDARY_SHARE_THRESHOLD,
) -> list[BoundaryMass]:
    """Share of rows sitting exactly at the column's max and min.

    In a continuous measurement one extreme value is rarely shared by many rows,
    so a share above `threshold` suggests the values were capped.
    """
    if not values:
        raise ValueError(f"{column}: cannot measure boundary mass of an empty column")
    if not 0 < threshold < 1:
        raise ValueError(f"threshold must be in (0, 1), got {threshold}")
    total_rows = len(values)
    measurements = []
    for side, boundary_value in (("max", max(values)), ("min", min(values))):
        row_count = sum(1 for value in values if value == boundary_value)
        share = row_count / total_rows
        measurements.append(BoundaryMass(column, side, boundary_value, row_count, share, share > threshold))
    return measurements
