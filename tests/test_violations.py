"""Quiet-hours violation analysis, CSV export, and the standalone honest HTML report."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from monitor.config import Config, QuietHours
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
        "within_quiet_hours",
        "quiet_window",
        "coarse_tag",
    ]
    assert len(rows) == 3  # header + 2 events
    assert rows[1][8] == "yes" and rows[1][-1] == "bark-like"  # 23:00 violates
    assert rows[2][8] == "no"  # 12:00 does not
    assert rows[1][9] == "22:00–08:00"
    assert rows[1][7] == "+0.0"  # no offsets given -> rows declare themselves raw


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


def test_window_label_wraps_24():
    # A 24-hour end wraps to 00; the label normalizes both bounds.
    report = compute_violations([], quiet_hours=QuietHours(22, 24), tz=timezone.utc)
    assert report.window == "22:00–00:00"


def test_config_quiet_hours_roundtrip_default():
    # The shipped default window is 22:00–08:00 (documented; reviewer-facing).
    assert Config().quiet_hours == QuietHours(22, 8)
