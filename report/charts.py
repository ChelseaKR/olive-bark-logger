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
        h = int(round((value / max_v) * chart_h)) if max_v else 0
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
