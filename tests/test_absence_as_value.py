"""Absence is written as absence, never as a confident number or a silent omission.

Three places in the report path rendered "no data" as something else:

1. A log with no events printed "Loudest peak: 0.0 dBFS". `summarize` returns 0.0 for
   the empty case, and 0.0 dBFS is digital full scale — the loudest reading the device
   can produce — so a silent log claimed maximum loudness. Same in the browser port.
2. When monitoring coverage could not be computed, the main report printed nothing
   where the coverage sentence goes, which reads as "the whole window was observed".
   The violations export already said "could not be determined"; the main report did not.
3. The calendar heatmap only had rows for days that had events. A quiet monitored day
   and a day the monitor was switched off both simply vanished from the calendar, so
   the hatched "not monitored" state (#52) could never apply to a whole missing day.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from monitor.config import Config
from monitor.detector import Event
from report.aggregate import summarize
from report.render import (
    COVERAGE_UNDETERMINED_NOTE,
    NO_EVENTS_VALUE,
    build_report,
    generate_report_from_db,
)
from report.render import main as report_main
from store import EventStore

DAY = datetime(2026, 3, 10, tzinfo=timezone.utc)


def _at(day_offset: int, hour: int) -> float:
    return DAY.timestamp() + day_offset * 86400 + hour * 3600


# --- 1. an empty log has no loudest peak ------------------------------------------------


def test_empty_report_does_not_print_full_scale_as_the_loudest_peak():
    config = Config(tz="UTC")
    summary = summarize([], quiet_hours=config.quiet_hours, tz=timezone.utc)
    assert summary.loudest_peak_dbfs == 0.0  # the sentinel summarize() returns
    html = build_report(summary, config=config, generated_at="2026-03-11 UTC")
    assert "0.0 dBFS" not in html
    assert f"<dt>Loudest peak</dt><dd>{NO_EVENTS_VALUE}</dd>" in html
    assert f"<dt>Mean peak</dt><dd>{NO_EVENTS_VALUE}</dd>" in html
    assert f"<dt>Longest event</dt><dd>{NO_EVENTS_VALUE}</dd>" in html
    assert "<dt>Total events</dt><dd>0</dd>" in html


def test_report_with_events_still_prints_real_peaks():
    config = Config(tz="UTC")
    events = [Event(_at(0, 22), _at(0, 22) + 3, 3.0, -18.0, -22.0)]
    summary = summarize(events, quiet_hours=config.quiet_hours, tz=timezone.utc)
    html = build_report(summary, config=config, generated_at="2026-03-11 UTC")
    assert "<dt>Loudest peak</dt><dd>-18.0 dBFS</dd>" in html
    assert f"<dd>{NO_EVENTS_VALUE}</dd>" not in html


# --- 2. undeterminable coverage is said, not omitted -------------------------------------


def test_main_report_states_when_coverage_cannot_be_determined(tmp_path):
    """Events only — no session, no gap. The coverage arithmetic has a span from the
    events themselves here, so drive `build_report` the way a caller without any
    coverage inputs does, and also the empty-log CLI path where nothing at all exists."""
    config = Config(tz="UTC")
    summary = summarize([], quiet_hours=config.quiet_hours, tz=timezone.utc)
    html = build_report(summary, config=config, generated_at="2026-03-11 UTC")
    assert COVERAGE_UNDETERMINED_NOTE in html

    db = tmp_path / "olive.db"
    EventStore(db).close()  # an empty store: nothing to measure a window from
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"db_path": str(db), "tz": "UTC"}))
    out = tmp_path / "r.html"
    assert report_main(["--config", str(cfg), "--out", str(out)]) == 0
    assert COVERAGE_UNDETERMINED_NOTE in out.read_text()


def test_main_report_states_coverage_when_it_can_be_computed(tmp_path):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        sid = store.start_session(
            started_at=_at(0, 22),
            device_label="pi-1",
            mic_model="m",
            placement_note="p",
            tz="UTC",
            calibration_offset=0.0,
            calibration_note="x",
            app_version="0.1.0",
        )
        store.add_event(Event(_at(0, 22) + 60, _at(0, 22) + 70, 10.0, -20.0, -25.0), session_id=sid)
        store.update_session(sid, frames_seen=36000, frames_dropped=0, ended_at=_at(0, 23))
    html = generate_report_from_db(str(db), Config(db_path=str(db), tz="UTC"), generated_at="x")
    assert "the device monitored 1.0 of 1.0 wall-clock hours" in html
    assert COVERAGE_UNDETERMINED_NOTE not in html


# --- 3. the calendar shows every day in the window ---------------------------------------


def _three_day_log(store) -> None:
    """Day 0: monitored, one event. Day 1: monitor off all day. Day 2: monitored, quiet
    (no events) until an event on day 3 closes the window. Before the fix the heatmap
    had rows for day 0 and day 3 only."""

    def session(start, end, events):
        sid = store.start_session(
            started_at=start,
            device_label="pi-1",
            mic_model="m",
            placement_note="p",
            tz="UTC",
            calibration_offset=0.0,
            calibration_note="x",
            app_version="0.1.0",
        )
        for t in events:
            store.add_event(Event(t, t + 5, 5.0, -20.0, -25.0), session_id=sid)
        store.update_session(sid, frames_seen=1, frames_dropped=0, ended_at=end)

    session(_at(0, 20), _at(0, 23), [_at(0, 21)])  # day 0
    # day 1: off air entirely
    session(_at(2, 0), _at(3, 12), [_at(3, 9)])  # day 2 quiet, day 3 one event


def test_heatmap_has_a_row_for_every_day_in_the_window(tmp_path):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        _three_day_log(store)
    html = generate_report_from_db(str(db), Config(db_path=str(db), tz="UTC"), generated_at="x")
    for day in ("2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13"):
        assert f'<th scope="row">{day}</th>' in html, f"{day} missing from the calendar"
    # The off-air day is hatched "not monitored" for every hour, not shown as quiet zeros.
    assert "2026-03-11 12:00 — not monitored" in html
    assert "2026-03-11 00:00 — not monitored" in html
    # The quiet monitored day is present and *not* marked unmonitored.
    assert "2026-03-12 12:00 — not monitored" not in html


def test_heatmap_rows_stay_in_calendar_order(tmp_path):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        _three_day_log(store)
    html = generate_report_from_db(str(db), Config(db_path=str(db), tz="UTC"), generated_at="x")
    calendar = html[html.index("<h2>Calendar heatmap</h2>") :]
    positions = [calendar.index(f'<th scope="row">2026-03-1{d}</th>') for d in range(4)]
    assert positions == sorted(positions)
