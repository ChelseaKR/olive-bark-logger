"""Structural accessibility gate for the report (the auto-checkable subset).

These checks cover the mechanical part of WCAG 2.2 AA that we can assert without a
browser: language, heading structure, a skip link, an image role + label on every
chart, a data-table equivalent for every chart, viewport meta, and reduced-motion
support. The manual screen-reader walkthrough is review-gated (see docs/audits).

`make a11y` additionally runs pa11y (axe) against rendered HTML when Node is present.
"""

from __future__ import annotations

import re

from monitor.config import Config
from monitor.detector import Event
from report.aggregate import summarize
from report.render import build_report


def _html():
    config = Config()
    start = 1_767_312_000.0
    events = [
        Event(
            start=start + i * 3600,
            end=start + i * 3600 + 4,
            duration=4.0,
            peak_level=-9.0,
            avg_level=-13.0,
        )
        for i in range(3)
    ]
    summary = summarize(events, quiet_hours=config.quiet_hours)
    return build_report(summary, config=config, generated_at="2026-01-01 00:00 UTC")


def test_has_lang_attribute():
    assert '<html lang="en">' in _html()


def test_has_viewport_meta():
    assert 'name="viewport"' in _html()


def test_exactly_one_h1():
    assert _html().count("<h1>") == 1


def test_has_skip_link():
    html = _html()
    assert 'class="skip"' in html and 'href="#main"' in html
    assert 'id="main"' in html


def test_every_chart_has_a_data_table():
    html = _html()
    figures = re.findall(r'<figure class="chart">.*?</figure>', html, re.DOTALL)
    assert figures, "no charts rendered"
    for fig in figures:
        assert "<table" in fig, "a chart is missing its data-table equivalent"
        assert "<caption>" in fig


def test_every_svg_has_role_and_label():
    html = _html()
    svgs = re.findall(r"<svg\b[^>]*>", html)
    assert svgs
    for svg in svgs:
        assert 'role="img"' in svg
        assert "aria-label=" in svg


def test_tables_use_scoped_headers():
    html = _html()
    assert 'scope="col"' in html and 'scope="row"' in html


def test_respects_reduced_motion():
    assert "prefers-reduced-motion" in _html()


def test_focus_is_visible():
    assert ":focus-visible" in _html()
