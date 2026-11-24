"""Static SVG figures for the article, rendered from experiment data.

SVG is written by hand to avoid a plotting dependency. Colours come from a
validated reference palette; each file carries its own light and dark values
because an SVG loaded through <img> cannot read the page's CSS variables.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape

from .questions import QuestionResult

BIN_WIDTH_DOLLARS = 5_000
HISTOGRAM_UPPER_DOLLARS = 500_000
SHIFT_QUESTION_IDS = ("Q1", "Q2", "Q4", "Q5")
UNDEFINED_SHIFT_QUESTION_ID = "Q3"

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


def _nice_ceiling(value: float) -> int:
    if value <= 0:
        raise ValueError("value must be positive")
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 3, 4, 5, 10):
        if value <= step * magnitude:
            return int(step * magnitude)
    return int(10 * magnitude)


AXIS_TICK_COUNT = 4
AXIS_HEADROOM = 1.1


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


def render_histogram(values: list[float], cap: float) -> str:
    counts, capped_count = bin_house_values(values, cap)
    frame = Frame(width=760, height=360, left=56, right=24, top=56, bottom=44)
    y_max, y_step = compute_nice_axis(max(max(counts), capped_count))
    slot_count = len(counts) + 3  # two empty slots of gap, then the cap bar
    slot = frame.plot_width / slot_count
    bar_width = max(slot - 1.5, 1.0)

    def y_of(count: float) -> float:
        return frame.top + frame.plot_height * (1 - count / y_max)

    parts = _open_svg(frame, f"Histogram of median house values; {capped_count} neighbourhoods at exactly ${cap:,.0f}")
    parts.append(f'<text class="ink title" x="{frame.left}" y="24">How many neighbourhoods have each median house value?</text>')
    parts.append(f'<text class="ink-2 small" x="{frame.left}" y="42">{len(values):,} neighbourhoods, grouped in $5,000 steps</text>')
    for tick in range(0, y_max + 1, y_step):
        y = y_of(tick)
        parts.append(f'<line class="grid" x1="{frame.left}" x2="{frame.width - frame.right}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="ink-2 small" x="{frame.left - 8}" y="{y + 4:.1f}" text-anchor="end">{tick:,}</text>')
    for index, count in enumerate(counts):
        if count:
            parts.append(_top_rounded_bar(frame.left + index * slot, y_of(count), bar_width, y_of(0) - y_of(count), "bar"))
    cap_x = frame.left + (slot_count - 1) * slot
    cap_top = y_of(capped_count)
    parts.append(_top_rounded_bar(cap_x, cap_top, bar_width, y_of(0) - cap_top, "cap"))
    parts.append(f'<text class="ink" x="{cap_x + bar_width:.1f}" y="{cap_top - 22:.1f}" text-anchor="end" font-weight="600">{capped_count} at exactly ${cap:,.0f}</text>')
    parts.append(f'<text class="ink-2 small" x="{cap_x + bar_width:.1f}" y="{cap_top - 7:.1f}" text-anchor="end">tallest normal bar: {max(counts)}</text>')
    parts.append(f'<line class="axis" x1="{frame.left}" x2="{frame.width - frame.right}" y1="{y_of(0):.1f}" y2="{y_of(0):.1f}"/>')
    for dollars in range(0, HISTOGRAM_UPPER_DOLLARS + 1, 100_000):
        x = frame.left + (dollars / BIN_WIDTH_DOLLARS) * slot
        parts.append(f'<text class="ink-2 small" x="{x:.1f}" y="{y_of(0) + 18:.1f}" text-anchor="middle">${dollars // 1000}k</text>')
    parts.append(f'<text class="ink-2 small" x="{cap_x + bar_width / 2:.1f}" y="{y_of(0) + 18:.1f}" text-anchor="middle">cap</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def compute_percent_shift(result: QuestionResult, multiplier: float) -> float:
    if result.observed_answer == 0:
        raise ValueError(f"{result.question_id}: percent shift is undefined when the observed answer is 0")
    return 100 * (result.answers_by_multiplier[multiplier] - result.observed_answer) / abs(result.observed_answer)


def render_shift_chart(results: list[QuestionResult], multipliers: tuple[float, ...], labels: dict[str, str]) -> str:
    scenario_multipliers = [multiplier for multiplier in multipliers if multiplier != 1.0]
    if len(scenario_multipliers) != 3:
        raise ValueError("the shift chart is designed for exactly three what-if multipliers")
    by_id = {result.question_id: result for result in results}
    missing = [question_id for question_id in (*SHIFT_QUESTION_IDS, UNDEFINED_SHIFT_QUESTION_ID) if question_id not in by_id]
    if missing:
        raise ValueError(f"missing question results: {missing}")

    frame = Frame(width=760, height=372, left=250, right=56, top=92, bottom=72)
    shifts = {qid: [compute_percent_shift(by_id[qid], m) for m in scenario_multipliers] for qid in SHIFT_QUESTION_IDS}
    x_max, x_step = compute_nice_axis(max(max(values) for values in shifts.values()))
    row_height = frame.plot_height / len(SHIFT_QUESTION_IDS)
    bar_height = 10.0
    series_classes = ("s1", "s2", "s3")

    def x_of(percent: float) -> float:
        return frame.left + frame.plot_width * percent / x_max

    parts = _open_svg(frame, "Percent change in each answer when capped homes are assumed to be worth more")
    parts.append(f'<text class="ink title" x="24" y="24">How much does each answer change?</text>')
    parts.append(f'<text class="ink-2 small" x="24" y="42">Change from the recorded answer if capped homes are really worth more than the cap</text>')
    legend_x = 24.0
    for multiplier, css_class in zip(scenario_multipliers, series_classes):
        parts.append(f'<rect class="{css_class}" x="{legend_x:.1f}" y="58" width="12" height="12" rx="2"/>')
        parts.append(f'<text class="ink small" x="{legend_x + 18:.1f}" y="68">worth {multiplier:g}× the cap</text>')
        legend_x += 150
    for tick in range(0, x_max + 1, x_step):
        x = x_of(tick)
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{frame.top}" y2="{frame.height - frame.bottom}"/>')
        parts.append(f'<text class="ink-2 small" x="{x:.1f}" y="{frame.height - frame.bottom + 18}" text-anchor="middle">+{tick}%</text>')
    for row, question_id in enumerate(SHIFT_QUESTION_IDS):
        row_top = frame.top + row * row_height
        label_y = row_top + row_height / 2 + 4
        parts.append(f'<text class="ink" x="{frame.left - 12}" y="{label_y:.1f}" text-anchor="end">{escape(labels[question_id])}</text>')
        if all(value == 0 for value in shifts[question_id]):
            parts.append(f'<text class="ink-2 small" x="{frame.left + 6}" y="{label_y:.1f}">no change in any scenario</text>')
            continue
        group_top = row_top + (row_height - 3 * bar_height - 4) / 2
        for index, (value, css_class) in enumerate(zip(shifts[question_id], series_classes)):
            y = group_top + index * (bar_height + 2)
            parts.append(f'<rect class="{css_class}" x="{frame.left}" y="{y:.1f}" width="{x_of(value) - frame.left:.1f}" height="{bar_height}" rx="2"/>')
        last_value = shifts[question_id][-1]
        last_y = group_top + 2 * (bar_height + 2) + bar_height - 1
        parts.append(f'<text class="ink small" x="{x_of(last_value) + 6:.1f}" y="{last_y:.1f}">+{last_value:.0f}%</text>')
    parts.append(f'<line class="axis" x1="{frame.left}" x2="{frame.left}" y1="{frame.top}" y2="{frame.height - frame.bottom}"/>')
    undefined = by_id[UNDEFINED_SHIFT_QUESTION_ID]
    upper = max(undefined.answers_by_multiplier.values())
    parts.append(
        f'<text class="ink-2 small" x="24" y="{frame.height - 30}">{escape(labels[UNDEFINED_SHIFT_QUESTION_ID])} is not shown: '
        f'it is recorded as 0%, so a % change can’t be computed.</text>'
    )
    parts.append(f'<text class="ink-2 small" x="24" y="{frame.height - 12}">Its true value lies somewhere between 0% and {upper:.2%}.</text>')
    parts.append("</svg>")
    return "\n".join(parts)
