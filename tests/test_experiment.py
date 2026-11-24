"""Integration: archive on disk -> checks -> questions -> report and JSON payload."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from clean_unfit.__main__ import VALUE_CAP, run_experiment
from clean_unfit.data import DataAcquisitionError, compute_sha256
from clean_unfit.report import build_json_payload, format_text_report
from tests.helpers import vary_row, write_archive


def to_csv(rows: list[tuple[float, ...]]) -> str:
    return "".join(",".join(f"{value:f}" for value in row) + "\n" for row in rows)


class RunExperimentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        rows = [vary_row(index, 150_000.0 + 20_000.0 * index, 2.0 + 0.6 * index) for index in range(20)]
        rows += [vary_row(100 + index, VALUE_CAP, 10.0) for index in range(3)]
        self.archive = write_archive(self.temp_dir / "cal_housing.tgz", to_csv(rows))

    def test_end_to_end_on_small_archive(self) -> None:
        _table, result = run_experiment(self.archive, expected_sha256=compute_sha256(self.archive))
        self.assertEqual(result.row_count, 23)
        self.assertTrue(result.is_generic_suite_passed)
        flagged = {(mass.column, mass.side) for mass in result.boundary_masses if mass.is_flagged}
        self.assertIn(("median_house_value", "max"), flagged)

        payload = build_json_payload(result)
        round_tripped = json.loads(json.dumps(payload, allow_nan=False))
        self.assertEqual([question["id"] for question in round_tripped["questions"]], ["Q1", "Q2", "Q3", "Q4", "Q5"])
        self.assertIn("Generic quality suite", format_text_report(result))

    def test_wrong_checksum_stops_the_run(self) -> None:
        with self.assertRaises(DataAcquisitionError):
            run_experiment(self.archive, expected_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
