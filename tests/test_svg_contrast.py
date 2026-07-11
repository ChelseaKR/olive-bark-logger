"""Merge-blocking: exact WCAG 2 contrast ratios for every SVG text/background pair.

Why this exists: axe-core cannot resolve the effective background of SVG <text> —
it returns every chart label as "needs further review", which pa11y surfaces as a
hard error (51 false positives on the demo report). Rather than trust a guess, this
test computes the WCAG 2 relative-luminance contrast ratio *exactly* for each
foreground/background pair the chart renderer can emit, and fails the merge if any
drops below 4.5:1 (AA, normal text). CI's pa11y step therefore excludes axe's
color-contrast rule for this document; computed HTML contrast stays blocking via
the htmlcs runner, and SVG contrast is enforced here — precisely, not heuristically.

Includes a canary (the repo's gate-hardening pattern): the pre-fix scheme — white
text on a 55%-intensity heatmap cell — must FAIL, proving this test detects the
defect class it guards against.
"""

from __future__ import annotations

from report.charts import (
    _AXIS_COLOR,
    _HEAT_EMPTY,
    _LABEL_FILL,
    _LABEL_HALO,
    _heat_fill,
    heatmap,
)

PAGE_BG = "#fff"  # report body background (report/render.py styles body #fff / #111)
AA_NORMAL = 4.5


def _channel(value: int) -> float:
    """sRGB 8-bit channel -> linear-light component (WCAG 2 definition)."""
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _luminance(color: str) -> float:
    r, g, b = (_channel(v) for v in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    """WCAG 2 contrast ratio between two opaque colors, in [1, 21]."""
    lighter, darker = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_axis_labels_pass_aa_on_page_background():
    # Bar-chart bucket labels and heatmap hour/day labels render _AXIS_COLOR
    # directly on the page background.
    assert contrast(_AXIS_COLOR, PAGE_BG) >= AA_NORMAL


def test_heatmap_count_glyph_passes_aa_against_its_halo():
    # In-cell counts are _LABEL_FILL glyphs painted over a _LABEL_HALO stroke
    # (paint-order="stroke"), so the adjacent background of every glyph is the
    # halo — at every cell shade (WCAG G18: contrast may be measured against a
    # halo that surrounds the letters).
    assert contrast(_LABEL_FILL, _LABEL_HALO) >= AA_NORMAL


def test_heatmap_label_markup_carries_the_halo():
    # Structural check: every in-cell count <text> actually ships the halo
    # attributes; without them the glyph sits on the raw cell fill, where
    # mid-intensity shades genuinely fail AA (see canary below).
    html = heatmap(
        chart_id="c",
        title="t",
        day_labels=["2026-01-01"],
        grid=[[0, 1, 2, 3] + [0] * 20],
    )
    count_labels = [
        part for part in html.split("<text ")[1:] if 'text-anchor="middle" fill="#111"' in part
    ]
    assert count_labels, "expected in-cell count labels in the heatmap"
    for label in count_labels:
        assert f'stroke="{_LABEL_HALO}"' in label
        assert 'paint-order="stroke"' in label


def test_empty_cell_shade_would_pass_if_ever_labeled():
    # Zero cells carry no text today; keep the invariant so a future change
    # that labels them cannot regress silently.
    assert contrast(_LABEL_FILL, _HEAT_EMPTY) >= AA_NORMAL


def test_canary_old_scheme_fails_on_mid_intensity_cells():
    # Pre-fix behavior: white text on cells with intensity ratio >= 0.55.
    # At 0.55 the mixed fill is far too light for white text — this must FAIL,
    # or this test could no longer catch the defect it exists to block.
    assert contrast("#fff", _heat_fill(0.55)) < AA_NORMAL


def test_heat_ramp_extremes_are_what_the_design_assumes():
    # The ramp mixes _HEAT_BASE over white: ratio 0 -> white, ratio 1 -> base.
    assert _heat_fill(0.0) == "#ffffff"
    assert _heat_fill(1.0) == "#3b6ea5"
