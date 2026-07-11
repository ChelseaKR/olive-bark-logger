"""Calendar heatmap: accessible day x hour grid with an equivalent data table.

The visual must never be color-only (counts appear as text + a data table) and the output
must be byte-stable, mirroring the bar-chart guarantees.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest
from monitor.config import Config, QuietHours
from monitor.detector import Event
from report.aggregate import summarize
from report.charts import heatmap
from report.render import build_report


def _ev(day: int, hour: int) -> Event:
    start = datetime(2026, 1, day, hour, tzinfo=timezone.utc).timestamp()
    return Event(start=start, end=start + 2.0, duration=2.0, peak_level=-9.0, avg_level=-13.0)


def test_heatmap_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        heatmap(chart_id="c", title="t", day_labels=["a"], grid=[])


def test_heatmap_rejects_non_24_rows():
    with pytest.raises(ValueError, match="24"):
        heatmap(chart_id="c", title="t", day_labels=["a"], grid=[[1, 2, 3]])


def test_heatmap_is_accessible_figure_with_table():
    grid = [[0] * 24, [0] * 24]
    grid[0][23] = 3
    grid[1][2] = 1
    html = heatmap(
        chart_id="cal", title="By day and hour", day_labels=["2026-01-01", "x"], grid=grid
    )
    # role/label image + a real data table (the a11y contract).
    assert 'role="img"' in html and "aria-label=" in html
    assert "<table" in html and "<caption>" in html
    assert 'scope="col"' in html and 'scope="row"' in html
    # Not color-only: the busiest cell's count is printed as SVG text and in the table.
    assert ">3<" in html
    # The aria-label names the busiest cell so screen-reader users get the headline.
    assert "Busiest" in html and "23:00 with 3" in html


def test_heatmap_table_has_24_hour_columns_and_totals():
    grid = [[1] * 24]
    html = heatmap(chart_id="cal", title="t", day_labels=["d"], grid=grid)
    table = re.search(r"<table.*?</table>", html, re.DOTALL).group(0)
    # 24 hour headers + Day + Total.
    assert table.count('scope="col"') == 26
    assert "<td>24</td>" in table  # row total


def test_heatmap_is_deterministic():
    grid = [[i % 3 for i in range(24)]]
    a = heatmap(chart_id="cal", title="t", day_labels=["d"], grid=grid)
    b = heatmap(chart_id="cal", title="t", day_labels=["d"], grid=grid)
    assert a == b


def test_empty_log_renders_calendar_placeholder():
    config = Config()
    summary = summarize([], quiet_hours=QuietHours(), tz=config.tzinfo())
    html = build_report(summary, config=config, generated_at="2026-01-01 00:00 UTC")
    assert "<h2>Calendar heatmap</h2>" in html
    assert "no calendar to show" in html


def test_report_includes_heatmap_when_events_exist():
    config = Config(tz="UTC")
    events = [_ev(1, 23), _ev(1, 23), _ev(2, 2)]
    summary = summarize(events, quiet_hours=config.quiet_hours, tz=config.tzinfo())
    html = build_report(summary, config=config, generated_at="2026-01-01 00:00 UTC")
    assert "<h2>Calendar heatmap</h2>" in html
    assert "Events by day and hour" in html
    # Both days appear as rows.
    assert "2026-01-01" in html and "2026-01-02" in html


def test_heatmap_renders_unmonitored_hatch_and_table_text():
    grid = [[0] * 24]
    grid[0][5] = 4  # a monitored, busy hour
    html = heatmap(
        chart_id="cal",
        title="t",
        day_labels=["2026-01-01"],
        grid=grid,
        unmonitored={("2026-01-01", 3)},
    )
    # The hatch pattern is defined and referenced for the unmonitored cell.
    assert '<pattern id="cal-unmon"' in html
    assert "url(#cal-unmon)" in html
    # Not color-only: the cell reads "not monitored" as text in the SVG title and table.
    assert "03:00 — not monitored" in html
    assert "<td>not monitored</td>" in html
    # The busy monitored hour still shows its count, and the empty monitored hours don't
    # claim to be unmonitored.
    assert ">4<" in html
    # Present in the SVG cell title, the aria-label, and the data table cell.
    assert html.count("not monitored") >= 2


def test_heatmap_unmonitored_excluded_from_row_total():
    grid = [[0] * 24]
    grid[0][1] = 2
    grid[0][2] = 3
    html = heatmap(
        chart_id="cal",
        title="t",
        day_labels=["d"],
        grid=grid,
        unmonitored={("d", 4)},  # an empty hour, marked not monitored
    )
    # Row total counts only monitored events (2 + 3), unaffected by the unmonitored cell.
    assert "<td>5</td>" in html


def test_report_shows_not_monitored_when_gaps_present(tmp_path):
    from datetime import datetime, timezone

    from report.render import generate_report_from_db
    from store import EventStore

    db = tmp_path / "olive.db"
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp()
    with EventStore(db) as store:
        # Two events on 2026-01-01 so the day appears as a heatmap row.
        for hour in (1, 20):
            store.add_event(_ev(1, hour))
        # An outage during hour 10 (no events there).
        store.add_gap(base + 10 * 3600, base + 10 * 3600 + 1800, "device-error")
    config = Config(tz="UTC")
    html = generate_report_from_db(str(db), config, generated_at="2026-01-01 00:00 UTC")
    assert "not monitored" in html
    assert "wall-clock hours" in html  # methodology coverage sentence


def test_summary_by_day_hour_grid():
    events = [_ev(1, 23), _ev(1, 23), _ev(2, 2)]
    s = summarize(events, quiet_hours=QuietHours(), tz=timezone.utc)
    assert s.by_day_hour["2026-01-01"][23] == 2
    assert s.by_day_hour["2026-01-02"][2] == 1
    # Each day row covers all 24 hours.
    assert set(s.by_day_hour["2026-01-01"].keys()) == set(range(24))
