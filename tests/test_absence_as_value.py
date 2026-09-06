"""Absence is written as absence, never as a confident number or a silent omission.

Four places in the report path rendered "no data" as something else:

1. A log with no events printed "Loudest peak: 0.0 dBFS". `summarize` returns 0.0 for
   the empty case, and 0.0 dBFS is digital full scale — the loudest reading the device
   can produce — so a silent log claimed maximum loudness. Same in the browser port.
2. When monitoring coverage could not be computed, the main report printed nothing
   where the coverage sentence goes, which reads as "the whole window was observed".
   The violations export already said "could not be determined"; the main report did not.
3. The calendar heatmap only had rows for days that had events. A quiet monitored day
   and a day the monitor was switched off both simply vanished from the calendar, so
   the hatched "not monitored" state (#52) could never apply to a whole missing day.
4. The quiet-hours duration rollup — the per-day table an ordinance's "30 minutes in a
   day" figure is actually read from, rendered ten lines from the heatmap it shares its
   days with — never learned (3). It listed only the days that had loud time in the
   window, so a night nothing was listening on vanished from it exactly as it used to
   vanish from the calendar; and with no quiet-hours event anywhere in the log the whole
   table was replaced by "there is nothing to roll up", which is a claim about what was
   measured made by a report that measured nothing.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from monitor.config import Config
from monitor.detector import Event
from report.aggregate import summarize
from report.charts import UNMONITORED_LABEL
from report.render import (
    COVERAGE_UNDETERMINED_NOTE,
    NO_EVENTS_VALUE,
    ROLLUP_ABSENCE_NOTE,
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


# --- 4. the per-day duration rollup covers every day, and names the unmonitored ones ---
#
# `_three_day_log` has no quiet-hours event anywhere in it, and one whole day (2026-03-11)
# with no monitor running at all. On the old code that combination rendered "No events
# fell within the quiet-hours window, so there is nothing to roll up" — a statement about
# what was observed, from a report that observed none of that night.


def _rollup_cells_of(html: str) -> dict[str, str]:
    """The rollup table as {day: cell text}, or {} when the table is not rendered."""
    if "Loud time within quiet hours, per day" not in html:
        return {}
    table = html.split("Loud time within quiet hours, per day")[1].split("</table>")[0]
    return dict(re.findall(r'<th scope="row">([^<]+)</th><td>([^<]*)</td>', table))


def test_rollup_names_the_unmonitored_night_instead_of_reporting_nothing(tmp_path):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        _three_day_log(store)
    html = generate_report_from_db(str(db), Config(db_path=str(db), tz="UTC"), generated_at="x")

    assert "nothing to roll up" not in html, (
        "a night with no monitor running was answered with 'nothing to roll up', which "
        "reads as a measured quiet night"
    )
    cells = _rollup_cells_of(html)
    assert set(cells) == {"2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13"}, (
        f"the rollup must cover every day the window covers, like the calendar: {cells}"
    )
    # The off-air day states the absence and carries no duration at all.
    assert cells["2026-03-11"] == UNMONITORED_LABEL
    # The monitored days state a measured zero, which is a finding, not an absence.
    assert cells["2026-03-12"] == "0 s"
    assert cells["2026-03-13"] == "0 s"
    # 2026-03-10's window closes at 23:00, so one of its quiet hours is uncovered and the
    # cell says which — a partly-covered night is neither "0 s" nor "not monitored".
    assert cells["2026-03-10"] == f"0 s (1 of 10 quiet hours {UNMONITORED_LABEL})"
    assert ROLLUP_ABSENCE_NOTE in html


def test_rollup_keeps_measured_durations_beside_the_unmonitored_days(tmp_path):
    """A real quiet-hours event on one night, no monitor at all on the next. The measured
    number must survive unchanged, and the unmonitored night must not become one."""
    db = tmp_path / "olive.db"
    common = {
        "device_label": "pi-1",
        "mic_model": "USB mic",
        "placement_note": "by the wall",
        "tz": "UTC",
        "calibration_offset": 0.0,
        "calibration_note": "x",
        "app_version": "0.1.0",
    }
    with EventStore(db) as store:
        first = store.start_session(started_at=_at(0, 22), **common)
        store.add_event(Event(_at(0, 23), _at(0, 23) + 600, 600.0, -12.0, -18.0), session_id=first)
        store.update_session(first, frames_seen=1, frames_dropped=0, ended_at=_at(1, 8))
        # 2026-03-11 22:00 -> 2026-03-12 08:00: nothing running, no gap row to show for it.
        second = store.start_session(started_at=_at(2, 22), **common)
        store.update_session(second, frames_seen=1, frames_dropped=0, ended_at=_at(3, 8))

    html = generate_report_from_db(str(db), Config(db_path=str(db), tz="UTC"), generated_at="x")
    cells = _rollup_cells_of(html)
    assert cells["2026-03-10"] == "10.0 min", "the measured duration must not move"
    # The unmonitored night is split across two dates by the same start-attribution the
    # durations use: 03-11's evening hours and 03-12's early-morning hours.
    assert UNMONITORED_LABEL in cells["2026-03-11"]
    assert UNMONITORED_LABEL in cells["2026-03-12"]
    assert "2026-03-13" in cells


def test_rollup_still_says_nothing_to_roll_up_when_that_is_the_whole_truth():
    """The prose fallback is not removed, only narrowed: a log the record shows as fully
    monitored with no quiet-hours loud time in it has genuinely nothing to roll up."""
    config = Config(tz="UTC")
    noon = _at(0, 12)
    summary = summarize(
        [Event(noon, noon + 5, 5.0, -20.0, -25.0)],
        quiet_hours=config.quiet_hours,
        tz=timezone.utc,
    )
    html = build_report(summary, config=config, generated_at="2026-03-11 UTC")
    assert "nothing to roll up" in html
    assert _rollup_cells_of(html) == {}
