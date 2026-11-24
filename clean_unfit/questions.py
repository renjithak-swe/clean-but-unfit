"""Questions asked of one dataset, evaluated under assumptions about capped values.

A value recorded at the cap only tells us the true value is >= cap. The true values
are unknown, so each question is evaluated under explicit scenarios where every capped
row's true value is `cap * multiplier`. These are sensitivity scenarios, not estimates
of the truth. If a question's answer does not move across scenarios, this data can
answer it. If the answer moves, the data cannot answer it without outside information.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Callable

from .data import Table

QuestionFunction = Callable[[list[float], list[float]], float]

HIGH_INCOME_THRESHOLD = 8.0  # dataset units of $10,000 (1990), i.e. $80k
LOWER_VALUE_THRESHOLD = 400_000.0
UPPER_VALUE_THRESHOLD = 600_000.0


def impute_capped_values(values: list[float], cap: float, multiplier: float) -> list[float]:
    if multiplier < 1:
        raise ValueError(f"multiplier must be >= 1 because a capped value is a lower bound, got {multiplier}")
    return [value * multiplier if value == cap else value for value in values]


def make_share_at_least(threshold: float) -> QuestionFunction:
    def compute_share(house_values: list[float], _incomes: list[float]) -> float:
        if not house_values:
            raise ValueError("cannot compute a share of an empty column")
        return sum(1 for value in house_values if value >= threshold) / len(house_values)

    return compute_share


def compute_median_value(house_values: list[float], _incomes: list[float]) -> float:
    return statistics.median(house_values)


def make_mean_value_for_income_at_least(min_income: float) -> QuestionFunction:
    def compute_mean(house_values: list[float], incomes: list[float]) -> float:
        subset = [value for value, income in zip(house_values, incomes) if income >= min_income]
        if not subset:
            raise ValueError(f"no rows with median_income >= {min_income}")
        return statistics.fmean(subset)

    return compute_mean


def compute_income_slope(house_values: list[float], incomes: list[float]) -> float:
    """OLS slope of median house value on median income (dollars per $10k of income)."""
    return statistics.linear_regression(incomes, house_values).slope


@dataclass(frozen=True)
class Question:
    question_id: str
    text: str
    compute: QuestionFunction


QUESTIONS: tuple[Question, ...] = (
    Question("Q1", "Median of district median house values", compute_median_value),
    Question("Q2", "Share of districts with median value >= $400k", make_share_at_least(LOWER_VALUE_THRESHOLD)),
    Question("Q3", "Share of districts with median value >= $600k", make_share_at_least(UPPER_VALUE_THRESHOLD)),
    Question(
        "Q4",
        "Mean median value in districts with median income >= $80k",
        make_mean_value_for_income_at_least(HIGH_INCOME_THRESHOLD),
    ),
    Question("Q5", "House value gained per +$10k median income (OLS slope)", compute_income_slope),
)


@dataclass(frozen=True)
class QuestionResult:
    question_id: str
    text: str
    answers_by_multiplier: dict[float, float]

    @property
    def observed_answer(self) -> float:
        """Answer at multiplier 1.0, i.e. computed on the data exactly as recorded."""
        return self.answers_by_multiplier[min(self.answers_by_multiplier)]

    @property
    def absolute_spread(self) -> float:
        answers = self.answers_by_multiplier.values()
        return max(answers) - min(answers)

    @property
    def relative_spread(self) -> float | None:
        """Spread divided by |observed answer|; None when the observed answer is 0."""
        if self.observed_answer == 0:
            return None
        return self.absolute_spread / abs(self.observed_answer)

    def is_materially_affected(self, relative_threshold: float) -> bool:
        if self.relative_spread is None:
            return self.absolute_spread > 0
        return self.relative_spread > relative_threshold


def evaluate_questions(
    table: Table,
    cap: float,
    multipliers: tuple[float, ...],
    questions: tuple[Question, ...] = QUESTIONS,
) -> list[QuestionResult]:
    if 1.0 not in multipliers:
        raise ValueError("multipliers must include 1.0 so the observed answer is reported")
    house_values = table.columns["median_house_value"]
    incomes = table.columns["median_income"]
    scenarios = {multiplier: impute_capped_values(house_values, cap, multiplier) for multiplier in multipliers}
    return [
        QuestionResult(
            question.question_id,
            question.text,
            {multiplier: question.compute(values, incomes) for multiplier, values in scenarios.items()},
        )
        for question in questions
    ]
