"""Static SVG figures for the article, rendered from experiment data.

SVG is written by hand to avoid a plotting dependency. Colours come from a
validated reference palette; each file carries its own light and dark values
because an SVG loaded through <img> cannot read the page's CSS variables.

Each chart has a wide layout for desktop and a narrow one for phones. Scaling a
wide chart down to a phone screen shrinks its text below a readable size, so the
narrow layout re-flows the content instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from html import escape

from .questions import QuestionResult

BIN_WIDTH_DOLLARS = 5_000
HISTOGRAM_UPPER_DOLLARS = 500_000
SHIFT_QUESTION_IDS = ("Q1", "Q2", "Q4", "Q5")
UNDEFINED_SHIFT_QUESTION_ID = "Q3"
AXIS_TICK_COUNT = 4
AXIS_HEADROOM = 1.1
CAP_SECTION_WIDTH = 52
BAR_HEIGHT = 10.0
BAR_GAP = 2.0
SERIES_CLASSES = ("s1", "s2", "s3")

STYLE = """
<style>
  .surface { fill: #fcfcfb; }
  .ink { fill: #0b0b0b; } .ink-2 { fill: #52514e; }
  .grid { stroke: #e4e3df; stroke-width: 1; }
  .axis { stroke: #b9b8b2; stroke-width: 1; }
  .bar { fill: #86b6ef; } .cap { fill: #eb6834; }
  .s1 { fill: #9ec5f4; } .s2 { fill: #3987e5; } .s3 { fill: #184f95; }
  text { font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; font-size: 13px; }
  .title { font-size: 15px; font-weight: 600; }
  .small { font-size: 12px; }
  @media (prefers-color-scheme: dark) {
    .surface { fill: #1a1a19; }
    .ink { fill: #f0efec; } .ink-2 { fill: #c3c2b7; }
    .grid { stroke: #2f2f2d; } .axis { stroke: #55544f; }
    .bar { fill: #3987e5; } .cap { fill: #d95926; }
    .s1 { fill: #6da7ec; } .s2 { fill: #3987e5; } .s3 { fill: #cde2fb; }
  }
</style>
"""


class Layout(Enum):
    WIDE = "wide"
    NARROW = "narrow"


@dataclass(frozen=True)
class Frame:
    width: int
    height: int
    left: int
    right: int
    top: int
    bottom: int

    @property
    def plot_width(self) -> int:
        return self.width - self.left - self.right

    @property
    def plot_height(self) -> int:
        return self.height - self.top - self.bottom


def _open_svg(frame: Frame, label: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {frame.width} {frame.height}" '
        f'role="img" aria-label="{escape(label)}">',
        STYLE,
        f'<rect class="surface" width="{frame.width}" height="{frame.height}"/>',
    ]


def _text_lines(lines: list[str], x: float, first_y: float, css_class: str, line_height: float) -> list[str]:
    return [
        f'<text class="{css_class}" x="{x:.1f}" y="{first_y + index * line_height:.1f}">{escape(line)}</text>'
        for index, line in enumerate(lines)
    ]


def _nice_ceiling(value: float) -> int:
    if value <= 0:
        raise ValueError("value must be positive")
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 3, 4, 5, 10):
        if value <= step * magnitude:
            return int(step * magnitude)
    return int(10 * magnitude)


def compute_nice_axis(max_value: float) -> tuple[int, int]:
    """Axis maximum and tick step, both whole numbers, with four evenly spaced ticks."""
    if max_value <= 0:
        raise ValueError("max_value must be positive")
    step = max(1, _nice_ceiling(max_value * AXIS_HEADROOM / AXIS_TICK_COUNT))
    return step * AXIS_TICK_COUNT, step


def _top_rounded_bar(x: float, y: float, width: float, height: float, css_class: str) -> str:
    # Round only the data end (top) so the bar still sits flat on the baseline.
    radius = min(2.0, width / 2, height)
    return (
        f'<path class="{css_class}" d="M{x:.2f},{y + height:.2f} V{y + radius:.2f} '
        f'Q{x:.2f},{y:.2f} {x + radius:.2f},{y:.2f} H{x + width - radius:.2f} '
        f'Q{x + width:.2f},{y:.2f} {x + width:.2f},{y + radius:.2f} V{y + height:.2f} Z"/>'
    )


def bin_house_values(values: list[float], cap: float) -> tuple[list[int], int]:
    """Counts per $5k bin up to $500k (top edge inclusive), plus the count at the cap."""
    if not values:
        raise ValueError("cannot bin an empty column")
    bin_count = HISTOGRAM_UPPER_DOLLARS // BIN_WIDTH_DOLLARS
    counts = [0] * bin_count
    capped_count = 0
    for value in values:
        if value == cap:
            capped_count += 1
            continue
        if value > HISTOGRAM_UPPER_DOLLARS:
            raise ValueError(f"uncapped value {value} exceeds the histogram range")
        counts[min(int(value // BIN_WIDTH_DOLLARS), bin_count - 1)] += 1
    return counts, capped_count


def render_histogram(values: list[float], cap: float, layout: Layout = Layout.WIDE) -> str:
    counts, capped_count = bin_house_values(values, cap)
    if layout is Layout.WIDE:
        frame = Frame(width=760, height=360, left=56, right=24, top=60, bottom=44)
        title_lines = ["How many neighbourhoods have each median house value?"]
    else:
        frame = Frame(width=360, height=380, left=44, right=12, top=84, bottom=40)
        title_lines = ["How many neighbourhoods have", "each median house value?"]
    subtitle_y = 24 + 18 * len(title_lines)
    y_max, y_step = compute_nice_axis(max(max(counts), capped_count))
    bins_width = frame.plot_width - CAP_SECTION_WIDTH
    slot = bins_width / len(counts)
    bar_width = max(slot - 1.0, 1.0)
    cap_bar_width = max(bar_width, 4.0)

    def y_of(count: float) -> float:
        return frame.top + frame.plot_height * (1 - count / y_max)

    def x_of_dollars(dollars: float) -> float:
        return frame.left + (dollars / BIN_WIDTH_DOLLARS) * slot

    parts = _open_svg(frame, f"Histogram of median house values; {capped_count} neighbourhoods at exactly ${cap:,.0f}")
    parts += _text_lines(title_lines, 16, 24, "ink title", 18)
    parts.append(f'<text class="ink-2 small" x="16" y="{subtitle_y}">{len(values):,} neighbourhoods, grouped in $5,000 steps</text>')
    for tick in range(0, y_max + 1, y_step):
        y = y_of(tick)
        parts.append(f'<line class="grid" x1="{frame.left}" x2="{frame.width - frame.right}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="ink-2 small" x="{frame.left - 6}" y="{y + 4:.1f}" text-anchor="end">{tick:,}</text>')
    for index, count in enumerate(counts):
        if count:
            parts.append(_top_rounded_bar(frame.left + index * slot, y_of(count), bar_width, y_of(0) - y_of(count), "bar"))
    cap_x = frame.width - frame.right - cap_bar_width
    cap_top = y_of(capped_count)
    parts.append(_top_rounded_bar(cap_x, cap_top, cap_bar_width, y_of(0) - cap_top, "cap"))
    label_right = frame.width - frame.right
    parts.append(f'<text class="ink" x="{label_right}" y="{cap_top - 22:.1f}" text-anchor="end" font-weight="600">{capped_count} at exactly ${cap:,.0f}</text>')
    parts.append(f'<text class="ink-2 small" x="{label_right}" y="{cap_top - 7:.1f}" text-anchor="end">tallest normal bar: {max(counts)}</text>')
    parts.append(f'<line class="axis" x1="{frame.left}" x2="{frame.width - frame.right}" y1="{y_of(0):.1f}" y2="{y_of(0):.1f}"/>')
    for dollars in range(0, HISTOGRAM_UPPER_DOLLARS + 1, 100_000):
        parts.append(
            f'<text class="ink-2 small" x="{x_of_dollars(dollars):.1f}" y="{y_of(0) + 18:.1f}" '
            f'text-anchor="middle">${dollars // 1000}k</text>'
        )
    parts.append(f'<text class="ink-2 small" x="{label_right}" y="{y_of(0) + 18:.1f}" text-anchor="end">cap</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def compute_percent_shift(result: QuestionResult, multiplier: float) -> float:
    if result.observed_answer == 0:
        raise ValueError(f"{result.question_id}: percent shift is undefined when the observed answer is 0")
    return 100 * (result.answers_by_multiplier[multiplier] - result.observed_answer) / abs(result.observed_answer)


@dataclass(frozen=True)
class ShiftData:
    multipliers: list[float]
    shifts: dict[str, list[float]]
    undefined_upper: float
    axis_max: int
    axis_step: int


def _prepare_shift_data(results: list[QuestionResult], multipliers: tuple[float, ...]) -> ShiftData:
    scenario_multipliers = [multiplier for multiplier in multipliers if multiplier != 1.0]
    if len(scenario_multipliers) != len(SERIES_CLASSES):
        raise ValueError("the shift chart is designed for exactly three what-if multipliers")
    by_id = {result.question_id: result for result in results}
    missing = [question_id for question_id in (*SHIFT_QUESTION_IDS, UNDEFINED_SHIFT_QUESTION_ID) if question_id not in by_id]
    if missing:
        raise ValueError(f"missing question results: {missing}")
    shifts = {qid: [compute_percent_shift(by_id[qid], m) for m in scenario_multipliers] for qid in SHIFT_QUESTION_IDS}
    axis_max, axis_step = compute_nice_axis(max(max(values) for values in shifts.values()))
    return ShiftData(
        multipliers=scenario_multipliers,
        shifts=shifts,
        undefined_upper=max(by_id[UNDEFINED_SHIFT_QUESTION_ID].answers_by_multiplier.values()),
        axis_max=axis_max,
        axis_step=axis_step,
    )


def _shift_bar_group(values: list[float], x0: float, plot_width: float, axis_max: int, top: float) -> list[str]:
    parts = []
    for index, (value, css_class) in enumerate(zip(values, SERIES_CLASSES)):
        y = top + index * (BAR_HEIGHT + BAR_GAP)
        parts.append(f'<rect class="{css_class}" x="{x0:.1f}" y="{y:.1f}" width="{plot_width * value / axis_max:.1f}" height="{BAR_HEIGHT}" rx="2"/>')
    last_y = top + 2 * (BAR_HEIGHT + BAR_GAP) + BAR_HEIGHT - 1
    parts.append(f'<text class="ink small" x="{x0 + plot_width * values[-1] / axis_max + 6:.1f}" y="{last_y:.1f}">+{values[-1]:.0f}%</text>')
    return parts


def _shift_axis(frame: Frame, data: ShiftData) -> list[str]:
    parts = []
    for tick in range(0, data.axis_max + 1, data.axis_step):
        x = frame.left + frame.plot_width * tick / data.axis_max
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{frame.top}" y2="{frame.height - frame.bottom}"/>')
        parts.append(f'<text class="ink-2 small" x="{x:.1f}" y="{frame.height - frame.bottom + 18}" text-anchor="middle">+{tick}%</text>')
    parts.append(f'<line class="axis" x1="{frame.left}" x2="{frame.left}" y1="{frame.top}" y2="{frame.height - frame.bottom}"/>')
    return parts


def render_shift_chart(
    results: list[QuestionResult],
    multipliers: tuple[float, ...],
    labels: dict[str, str],
    layout: Layout = Layout.WIDE,
) -> str:
    data = _prepare_shift_data(results, multipliers)
    if layout is Layout.WIDE:
        return _render_shift_wide(data, labels)
    return _render_shift_narrow(data, labels)


def _undefined_note(labels: dict[str, str], upper: float, layout: Layout) -> list[str]:
    name = labels[UNDEFINED_SHIFT_QUESTION_ID]
    if layout is Layout.WIDE:
        return [f"{name} is not shown: it is recorded as 0%, so a % change can’t be computed.",
                f"Its true value lies somewhere between 0% and {upper:.2%}."]
    return [f"{name} is not shown: it is recorded",
            "as 0%, so a % change can’t be computed.",
            f"Its true value lies between 0% and {upper:.2%}."]


def _render_shift_wide(data: ShiftData, labels: dict[str, str]) -> str:
    frame = Frame(width=760, height=372, left=250, right=56, top=92, bottom=72)
    row_height = frame.plot_height / len(SHIFT_QUESTION_IDS)
    parts = _open_svg(frame, "Percent change in each answer when capped homes are assumed to be worth more")
    parts.append('<text class="ink title" x="24" y="24">How much does each answer change?</text>')
    parts.append('<text class="ink-2 small" x="24" y="42">Change from the recorded answer if capped homes are really worth more than the cap</text>')
    legend_x = 24.0
    for multiplier, css_class in zip(data.multipliers, SERIES_CLASSES):
        parts.append(f'<rect class="{css_class}" x="{legend_x:.1f}" y="58" width="12" height="12" rx="2"/>')
        parts.append(f'<text class="ink small" x="{legend_x + 18:.1f}" y="68">worth {multiplier:g}× the cap</text>')
        legend_x += 150
    parts += _shift_axis(frame, data)
    group_height = 3 * BAR_HEIGHT + 2 * BAR_GAP
    for row, question_id in enumerate(SHIFT_QUESTION_IDS):
        row_top = frame.top + row * row_height
        label_y = row_top + row_height / 2 + 4
        parts.append(f'<text class="ink" x="{frame.left - 12}" y="{label_y:.1f}" text-anchor="end">{escape(labels[question_id])}</text>')
        values = data.shifts[question_id]
        if all(value == 0 for value in values):
            parts.append(f'<text class="ink-2 small" x="{frame.left + 6}" y="{label_y:.1f}">no change in any scenario</text>')
            continue
        parts += _shift_bar_group(values, frame.left, frame.plot_width, data.axis_max, row_top + (row_height - group_height) / 2)
    parts += _text_lines(_undefined_note(labels, data.undefined_upper, Layout.WIDE), 24, frame.height - 30, "ink-2 small", 18)
    parts.append("</svg>")
    return "\n".join(parts)


def _render_shift_narrow(data: ShiftData, labels: dict[str, str]) -> str:
    row_height = 62.0
    frame = Frame(width=360, height=int(118 + row_height * len(SHIFT_QUESTION_IDS) + 96), left=16, right=48, top=118, bottom=96)
    parts = _open_svg(frame, "Percent change in each answer when capped homes are assumed to be worth more")
    parts.append('<text class="ink title" x="16" y="24">How much does each answer change?</text>')
    parts += _text_lines(["Change from the recorded answer if capped", "homes are really worth more than the cap"], 16, 44, "ink-2 small", 16)
    parts.append('<text class="ink small" x="16" y="92">Capped homes worth:</text>')
    legend_x = 136.0
    for multiplier, css_class in zip(data.multipliers, SERIES_CLASSES):
        parts.append(f'<rect class="{css_class}" x="{legend_x:.1f}" y="82" width="12" height="12" rx="2"/>')
        parts.append(f'<text class="ink small" x="{legend_x + 16:.1f}" y="92">{multiplier:g}×</text>')
        legend_x += 56
    parts += _shift_axis(frame, data)
    for row, question_id in enumerate(SHIFT_QUESTION_IDS):
        row_top = frame.top + row * row_height
        parts.append(f'<text class="ink" x="{frame.left + 4}" y="{row_top + 16:.1f}">{escape(labels[question_id])}</text>')
        values = data.shifts[question_id]
        if all(value == 0 for value in values):
            parts.append(f'<text class="ink-2 small" x="{frame.left + 4}" y="{row_top + 36:.1f}">no change in any scenario</text>')
            continue
        parts += _shift_bar_group(values, frame.left, frame.plot_width, data.axis_max, row_top + 24)
    parts += _text_lines(_undefined_note(labels, data.undefined_upper, Layout.NARROW), 16, frame.height - 52, "ink-2 small", 16)
    parts.append("</svg>")
    return "\n".join(parts)
