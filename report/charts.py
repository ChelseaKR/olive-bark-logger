"""Deterministic inline-SVG bar charts, each paired with a data-table equivalent.

No plotting library: charts are hand-rendered SVG so output is byte-stable (snapshot
testable) and dependency-free. Accessibility is built in, not bolted on:

  * the SVG is role="img" with an aria-label summarizing it;
  * every chart is followed by a real <table> carrying the same numbers, so screen
    readers and keyboard users get the data without the graphic;
  * bars carry numeric labels — meaning never depends on color alone.
"""

from __future__ import annotations

from html import escape

_BAR_COLOR = "#3b6ea5"
_AXIS_COLOR = "#444"
_HEAT_BASE = (59, 110, 165)  # #3b6ea5 as RGB; cell shade mixes this over white by intensity
_HEAT_EMPTY = "#f5f5f5"  # zero-count cell: a light, neutral fill (kept distinct from shaded)


def bar_chart(
    *,
    chart_id: str,
    title: str,
    labels: list[str],
    values: list[float],
    value_caption: str,
) -> str:
    """Return an accessible <figure> with an SVG bar chart and an equivalent table."""
    if len(labels) != len(values):
        raise ValueError("labels and values must be the same length")

    max_v = max(values) if values and max(values) > 0 else 1.0
    bar_w = 24
    gap = 8
    chart_h = 160
    pad_bottom = 28
    pad_top = 12
    width = max(1, len(values)) * (bar_w + gap) + gap
    height = chart_h + pad_bottom + pad_top

    bars: list[str] = []
    for i, (label, value) in enumerate(zip(labels, values)):
        x = gap + i * (bar_w + gap)
        h = round((value / max_v) * chart_h) if max_v else 0
        y = pad_top + (chart_h - h)
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{_BAR_COLOR}">'
            f"<title>{escape(label)}: {_fmt(value)} {escape(value_caption)}</title></rect>"
        )
        bars.append(
            f'<text x="{x + bar_w / 2:.0f}" y="{height - pad_bottom + 16}" '
            f'font-size="9" text-anchor="middle" fill="{_AXIS_COLOR}">{escape(label)}</text>'
        )

    aria = f"{title}. {len(values)} bars. Maximum {_fmt(max_v)} {value_caption}."
    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{escape(aria)}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<line x1="{gap}" y1="{pad_top + chart_h}" x2="{width}" y2="{pad_top + chart_h}" '
        f'stroke="{_AXIS_COLOR}" stroke-width="1"/>' + "".join(bars) + "</svg>"
    )

    table = _table(chart_id, title, labels, values, value_caption)
    return f'<figure class="chart"><figcaption>{escape(title)}</figcaption>{svg}{table}</figure>'


def _table(
    chart_id: str, title: str, labels: list[str], values: list[float], value_caption: str
) -> str:
    rows = "".join(
        f'<tr><th scope="row">{escape(label)}</th><td>{_fmt(value)}</td></tr>'
        for label, value in zip(labels, values)
    )
    return (
        f'<table id="{escape(chart_id)}-table">'
        f"<caption>{escape(title)} — data table</caption>"
        f'<thead><tr><th scope="col">Bucket</th>'
        f'<th scope="col">{escape(value_caption)}</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def _fmt(value: float) -> str:
    """Stable numeric formatting: ints without a decimal, floats to one place."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _heat_fill(ratio: float) -> str:
    """Mix the base color over white by `ratio` in [0, 1] -> a stable #rrggbb string."""
    r, g, b = (round(255 - (255 - c) * ratio) for c in _HEAT_BASE)
    return f"#{r:02x}{g:02x}{b:02x}"


def heatmap(
    *,
    chart_id: str,
    title: str,
    day_labels: list[str],
    grid: list[list[int]],
    value_caption: str = "events",
) -> str:
    """Render a day x hour calendar heatmap as an accessible <figure>.

    `grid[i]` is the 24 hourly counts (hours 0..23) for `day_labels[i]`. The visual is
    not color-only: every non-zero cell also carries its numeric count as text, the cell
    has a <title> tooltip, the SVG is role="img" with a summarizing aria-label, and the
    whole grid is repeated as a real data table. Output is byte-stable for snapshotting.
    """
    if len(day_labels) != len(grid):
        raise ValueError("day_labels and grid must be the same length")
    if any(len(row) != 24 for row in grid):
        raise ValueError("each grid row must have 24 hourly values")

    max_v = max((max(row) for row in grid), default=0)
    cell_w = 22
    cell_h = 18
    gutter = 96  # left column for the date label
    top = 18  # row for the hour-of-day axis labels
    width = gutter + 24 * cell_w
    height = top + max(1, len(grid)) * cell_h

    parts: list[str] = []
    # Hour axis labels (00..23) along the top.
    for h in range(24):
        cx = gutter + h * cell_w + cell_w / 2
        parts.append(
            f'<text x="{cx:.0f}" y="12" font-size="8" text-anchor="middle" '
            f'fill="{_AXIS_COLOR}">{h:02d}</text>'
        )
    # One row of cells per day.
    busiest = ""
    for i, (label, row) in enumerate(zip(day_labels, grid)):
        y = top + i * cell_h
        parts.append(
            f'<text x="0" y="{y + cell_h - 5}" font-size="9" '
            f'fill="{_AXIS_COLOR}">{escape(label)}</text>'
        )
        for h, value in enumerate(row):
            x = gutter + h * cell_w
            ratio = (value / max_v) if max_v else 0.0
            fill = _HEAT_EMPTY if value == 0 else _heat_fill(ratio)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{fill}" '
                f'stroke="#fff" stroke-width="1">'
                f"<title>{escape(label)} {h:02d}:00 — {value} {escape(value_caption)}</title>"
                "</rect>"
            )
            if value:
                if value == max_v:
                    busiest = f"{label} {h:02d}:00 with {value} {value_caption}"
                # White text on the darkest cells, dark text on the lighter ones.
                text_fill = "#fff" if ratio >= 0.55 else "#111"
                parts.append(
                    f'<text x="{x + cell_w / 2:.0f}" y="{y + cell_h - 5}" font-size="9" '
                    f'text-anchor="middle" fill="{text_fill}">{value}</text>'
                )

    aria = (
        f"{title}. {len(grid)} days by 24 hours. Maximum {max_v} {value_caption} in a single hour."
    )
    if busiest:
        aria += f" Busiest: {busiest}."
    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{escape(aria)}" '
        f'xmlns="http://www.w3.org/2000/svg">' + "".join(parts) + "</svg>"
    )

    table = _heat_table(chart_id, title, day_labels, grid, value_caption)
    return f'<figure class="chart"><figcaption>{escape(title)}</figcaption>{svg}{table}</figure>'


def _heat_table(
    chart_id: str,
    title: str,
    day_labels: list[str],
    grid: list[list[int]],
    value_caption: str,
) -> str:
    head = "".join(f'<th scope="col">{h:02d}</th>' for h in range(24))
    rows: list[str] = []
    for label, row in zip(day_labels, grid):
        cells = "".join(f"<td>{v}</td>" for v in row)
        rows.append(f'<tr><th scope="row">{escape(label)}</th>{cells}<td>{sum(row)}</td></tr>')
    return (
        f'<table id="{escape(chart_id)}-table">'
        f"<caption>{escape(title)} — data table ({escape(value_caption)} per hour)</caption>"
        f'<thead><tr><th scope="col">Day</th>{head}'
        f'<th scope="col">Total</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
