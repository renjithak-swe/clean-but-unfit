from __future__ import annotations

import unittest

from clean_unfit.questions import (
    QuestionResult,
    compute_income_slope,
    evaluate_questions,
    impute_capped_values,
    make_mean_value_for_income_at_least,
    make_share_at_least,
)
from tests.helpers import make_table, vary_row

CAP = 500_001.0


class ImputeCappedValuesTest(unittest.TestCase):
    def test_scales_only_capped_values(self) -> None:
        self.assertEqual(impute_capped_values([100.0, CAP], CAP, 2.0), [100.0, CAP * 2])

    def test_multiplier_one_is_identity(self) -> None:
        values = [100.0, CAP]
        self.assertEqual(impute_capped_values(values, CAP, 1.0), values)

    def test_rejects_multiplier_below_one(self) -> None:
        with self.assertRaises(ValueError):
            impute_capped_values([CAP], CAP, 0.9)


class QuestionFunctionsTest(unittest.TestCase):
    def test_share_counts_threshold_inclusively(self) -> None:
        self.assertEqual(make_share_at_least(10.0)([5.0, 10.0, 15.0, 20.0], []), 0.75)

    def test_share_rejects_empty_input(self) -> None:
        with self.assertRaises(ValueError):
            make_share_at_least(10.0)([], [])

    def test_mean_filters_by_income(self) -> None:
        compute_mean = make_mean_value_for_income_at_least(8.0)
        self.assertEqual(compute_mean([100.0, 200.0, 300.0], [7.9, 8.0, 9.0]), 250.0)

    def test_mean_rejects_empty_subset(self) -> None:
        with self.assertRaises(ValueError):
            make_mean_value_for_income_at_least(8.0)([100.0], [1.0])

    def test_slope_recovers_known_line(self) -> None:
        incomes = [1.0, 2.0, 3.0, 4.0]
        self.assertAlmostEqual(compute_income_slope([10.0 + 5.0 * income for income in incomes], incomes), 5.0)


class QuestionResultTest(unittest.TestCase):
    def test_relative_spread_uses_observed_answer(self) -> None:
        result = QuestionResult("Q", "q", {1.0: 100.0, 2.0: 110.0})
        self.assertAlmostEqual(result.relative_spread or 0.0, 0.10)
        self.assertTrue(result.is_materially_affected(0.05))
        self.assertFalse(result.is_materially_affected(0.20))

    def test_zero_observed_answer_has_no_relative_spread(self) -> None:
        moved = QuestionResult("Q", "q", {1.0: 0.0, 2.0: 0.05})
        unmoved = QuestionResult("Q", "q", {1.0: 0.0, 2.0: 0.0})
        self.assertIsNone(moved.relative_spread)
        self.assertTrue(moved.is_materially_affected(0.05))
        self.assertFalse(unmoved.is_materially_affected(0.05))


class EvaluateQuestionsTest(unittest.TestCase):
    def setUp(self) -> None:
        uncapped = [vary_row(index, 100_000.0 + 10_000.0 * index, 2.0 + index * 0.5) for index in range(8)]
        capped = [vary_row(100 + index, CAP, 9.0) for index in range(2)]
        self.table = make_table(uncapped + capped)

    def test_question_below_cap_is_invariant_and_tail_question_moves(self) -> None:
        results = {result.question_id: result for result in evaluate_questions(self.table, CAP, (1.0, 1.5))}
        self.assertFalse(results["Q1"].is_materially_affected(0.05))
        self.assertFalse(results["Q2"].is_materially_affected(0.05))
        self.assertEqual(results["Q3"].observed_answer, 0.0)
        self.assertAlmostEqual(results["Q3"].answers_by_multiplier[1.5], 0.2)
        self.assertTrue(results["Q4"].is_materially_affected(0.05))
        self.assertTrue(results["Q5"].is_materially_affected(0.05))

    def test_requires_observed_scenario(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_questions(self.table, CAP, (1.5, 2.0))


if __name__ == "__main__":
    unittest.main()
