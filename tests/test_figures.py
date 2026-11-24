from __future__ import annotations

import unittest
import xml.etree.ElementTree as ElementTree

from clean_unfit.figures import (
    bin_house_values,
    compute_nice_axis,
    compute_percent_shift,
    render_histogram,
    render_shift_chart,
)
from clean_unfit.questions import QuestionResult

CAP = 500_001.0
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
LABELS = {"Q1": "Q1", "Q2": "Q2", "Q3": "Q3", "Q4": "Q4", "Q5": "Q5"}


def make_results() -> list[QuestionResult]:
    return [
        QuestionResult("Q1", "q1", {1.0: 100.0, 1.2: 100.0, 1.5: 100.0, 2.0: 100.0}),
        QuestionResult("Q2", "q2", {1.0: 0.1, 1.2: 0.1, 1.5: 0.1, 2.0: 0.1}),
        QuestionResult("Q3", "q3", {1.0: 0.0, 1.2: 0.05, 1.5: 0.05, 2.0: 0.05}),
        QuestionResult("Q4", "q4", {1.0: 100.0, 1.2: 110.0, 1.5: 130.0, 2.0: 170.0}),
        QuestionResult("Q5", "q5", {1.0: 10.0, 1.2: 11.0, 1.5: 12.0, 2.0: 16.0}),
    ]


class BinHouseValuesTest(unittest.TestCase):
    def test_separates_capped_values_and_bins_the_rest(self) -> None:
        counts, capped = bin_house_values([0.0, 4_999.0, 5_000.0, 500_000.0, CAP, CAP], CAP)
        self.assertEqual(len(counts), 100)
        self.assertEqual(counts[0], 2)
        self.assertEqual(counts[1], 1)
        self.assertEqual(counts[-1], 1)
        self.assertEqual(capped, 2)

    def test_rejects_empty_input(self) -> None:
        with self.assertRaises(ValueError):
            bin_house_values([], CAP)

    def test_rejects_uncapped_value_above_range(self) -> None:
        with self.assertRaises(ValueError):
            bin_house_values([600_000.0], CAP)


class RenderTest(unittest.TestCase):
    def test_histogram_is_valid_svg_with_labelled_cap(self) -> None:
        svg = render_histogram([100_000.0, 150_000.0, 150_000.0, CAP], CAP)
        root = ElementTree.fromstring(svg)
        self.assertEqual(root.tag, f"{SVG_NAMESPACE}svg")
        self.assertIn("1 at exactly $500,001", svg)

    def test_shift_chart_is_valid_svg_and_explains_undefined_question(self) -> None:
        svg = render_shift_chart(make_results(), (1.0, 1.2, 1.5, 2.0), LABELS)
        ElementTree.fromstring(svg)
        self.assertIn("+70%", svg)
        self.assertIn("no change in any scenario", svg)
        self.assertIn("between 0% and 5.00%", svg)

    def test_shift_chart_requires_three_scenarios(self) -> None:
        with self.assertRaises(ValueError):
            render_shift_chart(make_results(), (1.0, 2.0), LABELS)

    def test_shift_chart_requires_all_questions(self) -> None:
        with self.assertRaises(ValueError):
            render_shift_chart(make_results()[:3], (1.0, 1.2, 1.5, 2.0), LABELS)


class NiceAxisTest(unittest.TestCase):
    def test_small_counts_still_get_a_positive_step(self) -> None:
        self.assertEqual(compute_nice_axis(2), (4, 1))

    def test_large_counts_round_to_nice_steps(self) -> None:
        self.assertEqual(compute_nice_axis(965), (1200, 300))

    def test_rejects_non_positive_maximum(self) -> None:
        with self.assertRaises(ValueError):
            compute_nice_axis(0)


class PercentShiftTest(unittest.TestCase):
    def test_computes_relative_change(self) -> None:
        self.assertAlmostEqual(compute_percent_shift(make_results()[3], 2.0), 70.0)

    def test_undefined_for_zero_observed_answer(self) -> None:
        with self.assertRaises(ValueError):
            compute_percent_shift(make_results()[2], 2.0)


if __name__ == "__main__":
    unittest.main()
