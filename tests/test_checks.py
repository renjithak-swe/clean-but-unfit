from __future__ import annotations

import math
import unittest

from clean_unfit.checks import measure_boundary_mass, run_generic_suite
from clean_unfit.data import Table
from tests.helpers import VALID_ROW, make_table, vary_row


def failing_check_names(table: Table) -> list[str]:
    return [check.name for check in run_generic_suite(table) if not check.is_passed]


class GenericSuiteTest(unittest.TestCase):
    def test_clean_table_passes_every_check(self) -> None:
        table = make_table([vary_row(index, 200_000.0, 3.0) for index in range(5)])
        self.assertEqual(failing_check_names(table), [])

    def test_capped_values_pass_the_generic_suite(self) -> None:
        # The premise of the experiment: capping is invisible to question-agnostic checks.
        table = make_table([vary_row(index, 500_001.0, 9.0) for index in range(5)])
        self.assertEqual(failing_check_names(table), [])

    def test_detects_duplicates(self) -> None:
        self.assertEqual(failing_check_names(make_table([VALID_ROW, VALID_ROW])), ["uniqueness: no duplicate rows"])

    def test_detects_non_finite_values(self) -> None:
        row_with_nan = (*VALID_ROW[:-1], math.nan)
        self.assertIn("completeness: no NaN or infinite values", failing_check_names(make_table([row_with_nan])))

    def test_detects_out_of_range_coordinates(self) -> None:
        row_in_new_york = (-74.0, 40.7, *VALID_ROW[2:])
        self.assertEqual(failing_check_names(make_table([row_in_new_york])), ["range: longitude within California"])

    def test_detects_cross_field_inconsistency(self) -> None:
        more_bedrooms_than_rooms = (*VALID_ROW[:3], 10.0, 20.0, *VALID_ROW[5:])
        self.assertEqual(
            failing_check_names(make_table([more_bedrooms_than_rooms])),
            ["consistency: total_bedrooms <= total_rooms"],
        )

    def test_reports_unparsed_rows(self) -> None:
        table = make_table([VALID_ROW], unparsed_rows=[["bad"]])
        self.assertEqual(failing_check_names(table), ["parse: every row has 9 numeric fields"])

    def test_missing_column_short_circuits(self) -> None:
        table = Table(columns={"longitude": [1.0]}, unparsed_rows=[])
        results = run_generic_suite(table)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].is_passed)


class BoundaryMassTest(unittest.TestCase):
    def test_flags_pile_up_at_maximum(self) -> None:
        values = [float(value) for value in range(100)] + [500.0] * 5
        maximum, minimum = measure_boundary_mass(values, "value", threshold=0.01)
        self.assertTrue(maximum.is_flagged)
        self.assertEqual(maximum.row_count, 5)
        self.assertFalse(minimum.is_flagged)

    def test_share_equal_to_threshold_is_not_flagged(self) -> None:
        values = [1.0] + [float(value) for value in range(2, 101)]
        _, minimum = measure_boundary_mass(values, "value", threshold=0.01)
        self.assertAlmostEqual(minimum.share, 0.01)
        self.assertFalse(minimum.is_flagged)

    def test_constant_column_is_flagged_on_both_sides(self) -> None:
        self.assertTrue(all(mass.is_flagged for mass in measure_boundary_mass([3.0] * 10, "value")))

    def test_rejects_empty_column(self) -> None:
        with self.assertRaises(ValueError):
            measure_boundary_mass([], "value")

    def test_rejects_invalid_threshold(self) -> None:
        for threshold in (0.0, 1.0, -0.1):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                measure_boundary_mass([1.0, 2.0], "value", threshold=threshold)


if __name__ == "__main__":
    unittest.main()
