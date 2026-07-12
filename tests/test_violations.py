"""Quiet-hours violation analysis, CSV export, and the standalone honest HTML report."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from monitor.config import Config, QuietHours, QuietSchedule
from monitor.detector import Event
from report.render import main as report_main
from report.violations import (
    NO_SOURCE_NOTE,
    build_violation_report_html,
    compute_violations,
    violations_to_csv,
)
from store import EventStore


def _ev(hour: int, day: int = 1, duration: float = 2.0, tag: str | None = None) -> Event:
    start = datetime(2026, 1, day, hour, tzinfo=timezone.utc).timestamp()
    return Event(
        start=start,
        end=start + duration,
        duration=duration,
        peak_level=-8.0,
        avg_level=-12.0,
        coarse_tag=tag,
    )


def _ev_at(dt: datetime, duration: float) -> Event:
    start = dt.timestamp()
    return Event(
        start=start,
        end=start + duration,
        duration=duration,
        peak_level=-8.0,
        avg_level=-12.0,
    )


def test_seconds_within_quiet_hours_prorates_boundary():
    # 120 s event straddling the 22:00 quiet-hours start: begins at 21:59:00, so exactly
    # 60 s fall inside the window and 60 s fall outside.
    qh = QuietHours(22, 8)
    ev = _ev_at(datetime(2026, 1, 1, 21, 59, 0, tzinfo=timezone.utc), 120.0)
    report = compute_violations([ev], quiet_hours=qh, tz=timezone.utc)
    row = report.rows[0]
    assert row.within_quiet_hours is False  # start (21:59) is outside quiet hours
    assert row.seconds_within_quiet_hours == 60.0
    assert report.within_loud_seconds == 60.0
    assert report.outside_loud_seconds == 60.0


def test_seconds_within_quiet_hours_fully_inside_and_outside():
    qh = QuietHours(22, 8)
    inside = _ev_at(datetime(2026, 1, 1, 23, 0, 0, tzinfo=timezone.utc), 30.0)
    outside = _ev_at(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc), 3600.0)
    report = compute_violations([inside, outside], quiet_hours=qh, tz=timezone.utc)
    assert report.rows[0].seconds_within_quiet_hours == 30.0  # full duration
    assert report.rows[1].seconds_within_quiet_hours == 0.0  # long, but wholly outside


def test_seconds_within_quiet_hours_midnight_wrap():
    # Window 22->8 wraps midnight; an event from 23:59:30 to 00:00:30 is entirely inside.
    qh = QuietHours(22, 8)
    ev = _ev_at(datetime(2026, 1, 1, 23, 59, 30, tzinfo=timezone.utc), 60.0)
    report = compute_violations([ev], quiet_hours=qh, tz=timezone.utc)
    assert report.rows[0].seconds_within_quiet_hours == 60.0


def test_compute_violations_counts_within_and_outside():
    events = [_ev(23), _ev(2), _ev(12)]  # two inside 22-08, one outside
    report = compute_violations(events, quiet_hours=QuietHours(22, 8), tz=timezone.utc)
    assert report.total_events == 3
    assert report.within_count == 2
    assert report.outside_count == 1
    assert report.within_loud_seconds == 4.0
    assert report.outside_loud_seconds == 2.0
    assert report.window == "22:00–08:00"
    # Every event is represented, flagged honestly (not just the violations).
    assert [r.within_quiet_hours for r in report.rows] == [True, True, False]


def test_compute_violations_empty():
    report = compute_violations([], quiet_hours=QuietHours(), tz=timezone.utc)
    assert report.total_events == 0
    assert report.within_count == 0 and report.outside_count == 0
    assert report.rows == []


def test_compute_violations_carries_event_anatomy():
    event = Event(
        start=datetime(2026, 1, 1, 23, tzinfo=timezone.utc).timestamp(),
        end=datetime(2026, 1, 1, 23, 0, 2, tzinfo=timezone.utc).timestamp(),
        duration=2.0,
        peak_level=-8.0,
        avg_level=-12.0,
        rise_time_s=0.4,
        loud6_s=1.6,
        longest_run_s=1.9,
    )
    report = compute_violations([event], quiet_hours=QuietHours(22, 8), tz=timezone.utc)
    row = report.rows[0]
    assert (row.rise_time_s, row.loud6_s, row.longest_run_s) == (0.4, 1.6, 1.9)


def test_violations_csv_lists_all_events_flagged(tmp_path):
    out = tmp_path / "violations.csv"
    events = [_ev(23, tag="bark-like"), _ev(12)]
    n = violations_to_csv(events, out, quiet_hours=QuietHours(22, 8), tz=timezone.utc)
    assert n == 2
    text = out.read_text()
    # R1: the "what this can and cannot prove" cover travels as a leading comment preamble;
    # the machine-readable data rows below it are unchanged.
    assert "# What this can and cannot prove" in text
    data_lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    rows = list(csv.reader(data_lines))
    assert rows[0] == [
        "start_unix",
        "start_iso",
        "end_iso",
        "hour_local",
        "duration_s",
        "peak_dbfs",
        "avg_dbfs",
        "calibration_offset_db",
        "rise_time_s",
        "loud6_s",
        "longest_run_s",
        "within_quiet_hours",
        "seconds_within_quiet_hours",
        "quiet_window",
        "monitored",
        "coarse_tag",
    ]
    assert len(rows) == 3  # header + 2 events
    header = rows[0]
    within = header.index("within_quiet_hours")
    seconds = header.index("seconds_within_quiet_hours")
    window = header.index("quiet_window")
    monitored = header.index("monitored")
    offset = header.index("calibration_offset_db")
    assert rows[1][within] == "yes" and rows[1][-1] == "bark-like"  # 23:00 violates
    assert rows[2][within] == "no"  # 12:00 does not
    # The pro-rated seconds column sits between the flag and the window label.
    assert rows[1][seconds] == "2.0"  # 2 s event fully inside quiet hours
    assert rows[2][seconds] == "0.0"  # noon event contributes no quiet seconds
    assert rows[1][window] == "22:00–08:00"
    assert rows[1][offset] == "+0.0"  # no offsets given -> rows declare themselves raw
    assert rows[1][monitored] == "yes" and rows[2][monitored] == "yes"


def test_violations_csv_flags_unmonitored_events(tmp_path):
    from store import Gap

    out = tmp_path / "violations.csv"
    events = [_ev(23), _ev(12)]
    gap = Gap(
        id=1,
        session_id=None,
        start=events[0].start - 1,
        end=events[0].end + 1,
        reason="shutdown",
    )
    violations_to_csv(events, out, quiet_hours=QuietHours(22, 8), tz=timezone.utc, gaps=[gap])
    data_lines = [ln for ln in out.read_text().splitlines() if not ln.startswith("#")]
    rows = list(csv.reader(data_lines))
    mon = rows[0].index("monitored")
    assert rows[1][mon] == "no"  # the 23:00 event overlaps the gap
    assert rows[2][mon] == "yes"


def test_violation_html_is_honest_and_accessible():
    report = compute_violations([_ev(23)], quiet_hours=QuietHours(22, 8), tz=timezone.utc)
    html = build_violation_report_html(
        report,
        threshold_dbfs=-35.0,
        min_duration_s=0.4,
        generated_at="2026-01-01 UTC",
        calibrated=False,
    )
    assert '<html lang="en">' in html
    assert "No audio was recorded" in html
    assert NO_SOURCE_NOTE in html
    assert "not proof" in html  # the scope note: a flag is not proof of source
    assert "<h2>Methodology</h2>" in html and "<h2>Limitations</h2>" in html
    assert 'scope="col"' in html and 'scope="row"' in html
    assert "No calibration offset is applied" in html
    # R1 cover + R5 reader-facing no-audio note travel with the shared artifact.
    assert "<h2>What this can and cannot prove</h2>" in html
    assert "<h2>Why there is deliberately no audio</h2>" in html
    assert "deliberate privacy choice, not missing data" in html


def test_violation_html_multi_epoch_is_disclosed_per_row():
    """A window spanning calibration epochs discloses per-row offsets and never claims a
    single uniform calibration state (honest-report invariant on the export surface)."""
    events = [_ev(23), _ev(2)]
    report = compute_violations(
        events, quiet_hours=QuietHours(22, 8), tz=timezone.utc, offsets_db=[0.0, 12.0]
    )
    assert [r.calibration_offset_db for r in report.rows] == [0.0, 12.0]
    html = build_violation_report_html(
        report,
        threshold_dbfs=-35.0,
        min_duration_s=0.4,
        generated_at="2026-01-01 UTC",
        calibrated=False,
        multi_epoch=True,
    )
    assert "more than one calibration epoch" in html
    assert "+0.0" in html and "+12.0" in html  # per-row offsets visible in the table
    assert "Calibration offset (dB)" in html
    # Neither uniform claim is made for a mixed window.
    assert "No calibration offset is applied" not in html
    assert "A calibration offset is applied" not in html


def test_violation_html_empty_log():
    report = compute_violations([], quiet_hours=QuietHours(), tz=timezone.utc)
    html = build_violation_report_html(
        report,
        threshold_dbfs=-35.0,
        min_duration_s=0.4,
        generated_at="2026-01-01 UTC",
        calibrated=True,
    )
    assert "nothing to flag" in html
    assert "calibration offset is applied" in html


def test_report_cli_exports_violations(tmp_path, capsys):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        store.add_event(_ev(23))
        store.add_event(_ev(12))
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "db_path": str(db),
                "tz": "UTC",
                "quiet_hours": {"start_hour": 22, "end_hour": 8},
            }
        ),
        encoding="utf-8",
    )
    vcsv = tmp_path / "v.csv"
    vhtml = tmp_path / "v.html"
    rc = report_main(
        [
            "--config",
            str(config_path),
            "--db",
            str(db),
            "--out",
            str(tmp_path / "r.html"),
            "--violations-csv",
            str(vcsv),
            "--violations-html",
            str(vhtml),
            "--generated-at",
            "2026-01-01 UTC",
        ]
    )
    assert rc == 0
    assert vcsv.exists()
    data_lines = [ln for ln in vcsv.read_text().splitlines() if not ln.startswith("#")]
    assert len(data_lines) == 3  # header + 2 events, excluding the R1 cover preamble
    assert vhtml.exists() and "Quiet-Hours Report" in vhtml.read_text()
    out = capsys.readouterr().out
    assert "v.csv" in out and "v.html" in out
    # The deprecated {start_hour, end_hour} form is auto-upgraded to a QuietSchedule
    # equivalent to the legacy daily 22:00 -> 08:00 window.
    upgraded = Config.load(config_path).quiet_hours
    assert isinstance(upgraded, QuietSchedule)
    assert upgraded == QuietSchedule.from_legacy(22, 8)
    assert upgraded.label() == "22:00–08:00"


def test_window_label_wraps_24():
    # A 24-hour end wraps to 00; the label normalizes both bounds.
    report = compute_violations([], quiet_hours=QuietHours(22, 24), tz=timezone.utc)
    assert report.window == "22:00–00:00"


def test_config_quiet_hours_roundtrip_default():
    # The shipped default window is 22:00–08:00 (documented; reviewer-facing).
    assert Config().quiet_hours == QuietHours(22, 8)
