"""Turn experiment results into a readable text report and a JSON-serialisable payload."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .checks import BoundaryMass, CheckResult
from .questions import QuestionResult


@dataclass(frozen=True)
class ExperimentResult:
    row_count: int
    value_cap: float
    multipliers: tuple[float, ...]
    material_threshold: float
    generic_checks: list[CheckResult]
    boundary_masses: list[BoundaryMass]
    question_results: list[QuestionResult]

    @property
    def is_generic_suite_passed(self) -> bool:
        return all(check.is_passed for check in self.generic_checks)


def _format_answer(answer: float) -> str:
    return f"{answer:.2%}" if 0 <= answer < 1 else f"{answer:,.0f}"


def format_text_report(result: ExperimentResult) -> str:
    lines = [f"rows: {result.row_count}", "", "Generic quality suite"]
    lines += [
        f"  [{'PASS' if check.is_passed else 'FAIL'}] {check.name}: {check.failing_rows} of {check.total_rows} rows fail"
        for check in result.generic_checks
    ]
    lines += ["", "Boundary-mass check (rows sitting exactly at a column's min or max)"]
    lines += [
        f"  [FLAG] {mass.column} {mass.side}={mass.value:g}: {mass.row_count} rows ({mass.share:.2%})"
        for mass in result.boundary_masses
        if mass.is_flagged
    ]
    lines += ["", f"Questions under scenarios: values at ${result.value_cap:,.0f} replaced by cap x multiplier"]
    header = ["id", *[f"x{multiplier:g}" for multiplier in result.multipliers], "rel. spread", "affected", "question"]
    lines.append("  " + " | ".join(header))
    for question in result.question_results:
        answers = [_format_answer(question.answers_by_multiplier[multiplier]) for multiplier in result.multipliers]
        spread = "n/a (observed 0)" if question.relative_spread is None else f"{question.relative_spread:.1%}"
        affected = "yes" if question.is_materially_affected(result.material_threshold) else "no"
        lines.append("  " + " | ".join([question.question_id, *answers, spread, affected, question.text]))
    return "\n".join(lines)


def build_json_payload(result: ExperimentResult) -> dict[str, Any]:
    return {
        "row_count": result.row_count,
        "value_cap": result.value_cap,
        "multipliers": list(result.multipliers),
        "material_threshold": result.material_threshold,
        "is_generic_suite_passed": result.is_generic_suite_passed,
        "generic_checks": [asdict(check) for check in result.generic_checks],
        "boundary_masses": [asdict(mass) for mass in result.boundary_masses],
        "questions": [
            {
                "id": question.question_id,
                "text": question.text,
                "answers_by_multiplier": {str(multiplier): answer for multiplier, answer in question.answers_by_multiplier.items()},
                "observed_answer": question.observed_answer,
                "absolute_spread": question.absolute_spread,
                "relative_spread": question.relative_spread,
                "is_materially_affected": question.is_materially_affected(result.material_threshold),
            }
            for question in result.question_results
        ],
    }
