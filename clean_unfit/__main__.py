"""Run the clean-but-unfit experiment.

Usage: python -m clean_unfit [--data-dir data] [--out results]
Exit codes: 0 success, 1 generic suite failed (the "clean" premise does not hold), 2 data error.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .checks import POSITIVE_COLUMNS, measure_boundary_mass, run_generic_suite
from .data import SOURCE_SHA256, DataAcquisitionError, Table, download_archive, load_table
from .figures import render_histogram, render_shift_chart
from .questions import evaluate_questions
from .report import ExperimentResult, build_json_payload, format_text_report

ARCHIVE_FILENAME = "cal_housing.tgz"
RESULTS_FILENAME = "results.json"
HISTOGRAM_FILENAME = "house-value-histogram.svg"
SHIFT_CHART_FILENAME = "answer-shifts.svg"
CHART_LABELS = {
    "Q1": "Q1 · median value",
    "Q2": "Q2 · share worth $400k+",
    "Q3": "Q3 (share worth $600k+)",
    "Q4": "Q4 · avg value, high-income areas",
    "Q5": "Q5 · value per +$10k income",
}
VALUE_CAP = 500_001.0
SCENARIO_MULTIPLIERS = (1.0, 1.2, 1.5, 2.0)
MATERIAL_RELATIVE_SPREAD = 0.05

EXIT_OK = 0
EXIT_PREMISE_FAILED = 1
EXIT_DATA_ERROR = 2

logger = logging.getLogger("clean_unfit")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            entry["context"] = context
        return json.dumps(entry)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)


def run_experiment(archive_path: Path, expected_sha256: str = SOURCE_SHA256) -> tuple[Table, ExperimentResult]:
    table = load_table(download_archive(archive_path, expected_sha256=expected_sha256))
    return table, analyze_table(table)


def analyze_table(table: Table) -> ExperimentResult:
    boundary_masses = [
        mass for column in POSITIVE_COLUMNS for mass in measure_boundary_mass(table.columns[column], column)
    ]
    return ExperimentResult(
        row_count=table.row_count,
        value_cap=VALUE_CAP,
        multipliers=SCENARIO_MULTIPLIERS,
        material_threshold=MATERIAL_RELATIVE_SPREAD,
        generic_checks=run_generic_suite(table),
        boundary_masses=boundary_masses,
        question_results=evaluate_questions(table, VALUE_CAP, SCENARIO_MULTIPLIERS),
    )


def write_figures(table: Table, result: ExperimentResult, out_dir: Path) -> None:
    (out_dir / HISTOGRAM_FILENAME).write_text(
        render_histogram(table.columns["median_house_value"], result.value_cap), encoding="utf-8"
    )
    (out_dir / SHIFT_CHART_FILENAME).write_text(
        render_shift_chart(result.question_results, result.multipliers, CHART_LABELS), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean but unfit: which questions can a clean dataset answer?")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="where the archive is cached")
    parser.add_argument("--out", type=Path, default=Path("results"), help="where results.json is written")
    args = parser.parse_args(argv)
    configure_logging()

    try:
        table, result = run_experiment(args.data_dir / ARCHIVE_FILENAME)
    except DataAcquisitionError as error:
        logger.error("data acquisition failed", extra={"context": {"reason": str(error)}})
        return EXIT_DATA_ERROR

    print(format_text_report(result))
    args.out.mkdir(parents=True, exist_ok=True)
    results_path = args.out / RESULTS_FILENAME
    results_path.write_text(json.dumps(build_json_payload(result), indent=2), encoding="utf-8")
    write_figures(table, result, args.out)
    logger.info("results written", extra={"context": {"path": str(results_path)}})
    return EXIT_OK if result.is_generic_suite_passed else EXIT_PREMISE_FAILED


if __name__ == "__main__":
    sys.exit(main())
