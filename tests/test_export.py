"""CSV export of the event log, directly and via the report CLI."""

from __future__ import annotations

import csv

import pytest
from monitor.detector import Event
from report.export import events_to_csv
from report.render import main as report_main
from store import EventStore


def _events():
    return [
        Event(1_767_312_000.0, 1_767_312_004.0, 4.0, -8.0, -12.0, coarse_tag="bark-like"),
        Event(1_767_315_600.0, 1_767_315_601.5, 1.5, -20.0, -24.0),
    ]


def test_events_to_csv_writes_header_and_rows(tmp_path):
    out = tmp_path / "events.csv"
    n = events_to_csv(_events(), out)
    assert n == 2
    rows = list(csv.reader(out.read_text().splitlines()))
    assert rows[0] == [
        "start_unix",
        "start_iso",
        "end_iso",
        "duration_s",
        "peak_dbfs",
        "avg_dbfs",
        "calibration_offset_db",
        "monitored",
        "rise_time_s",
        "loud6_s",
        "longest_run_s",
        "coarse_tag",
    ]
    assert len(rows) == 3  # header + 2
    assert rows[1][-1] == "bark-like"
    assert rows[2][-1] == ""  # untagged event -> empty tag
    # Without offsets_db the levels are raw: the offset column says so explicitly.
    assert rows[1][6] == "+0.0" and rows[2][6] == "+0.0"
    # With no gaps supplied, every event is reported as monitored.
    monitored = rows[0].index("monitored")
    assert rows[1][monitored] == "yes" and rows[2][monitored] == "yes"


def test_events_to_csv_writes_anatomy_and_blanks_legacy_values(tmp_path):
    out = tmp_path / "events.csv"
    events = [
        Event(1.0, 3.0, 2.0, -8.0, -12.0, rise_time_s=0.4, loud6_s=1.6, longest_run_s=1.9),
        Event(4.0, 5.0, 1.0, -9.0, -13.0),
    ]
    events_to_csv(events, out)
    rows = list(csv.DictReader(out.read_text().splitlines()))
    assert rows[0]["rise_time_s"] == "0.4"
    assert rows[0]["loud6_s"] == "1.6"
    assert rows[0]["longest_run_s"] == "1.9"
    assert rows[1]["rise_time_s"] == ""
    assert rows[1]["loud6_s"] == ""
    assert rows[1]["longest_run_s"] == ""


def test_events_to_csv_records_per_row_offsets(tmp_path):
    out = tmp_path / "events.csv"
    n = events_to_csv(_events(), out, offsets_db=[6.5, 0.0])
    assert n == 2
    rows = list(csv.reader(out.read_text().splitlines()))
    assert rows[1][6] == "+6.5"  # calibrated row is self-describing
    assert rows[2][6] == "+0.0"  # raw row too

    with pytest.raises(ValueError):
        events_to_csv(_events(), out, offsets_db=[6.5])  # must parallel events


def test_events_to_csv_marks_events_in_a_gap_unmonitored(tmp_path):
    from store import Gap

    out = tmp_path / "events.csv"
    evs = _events()
    # A gap covering the first event's span only.
    gap = Gap(
        id=1, session_id=None, start=evs[0].start - 1, end=evs[0].end + 1, reason="device-error"
    )
    events_to_csv(evs, out, gaps=[gap])
    rows = list(csv.reader(out.read_text().splitlines()))
    mon_idx = rows[0].index("monitored")
    assert rows[1][mon_idx] == "no"  # overlaps the gap
    assert rows[2][mon_idx] == "yes"  # outside the gap


def test_report_cli_also_exports_csv(tmp_path, capsys):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for ev in _events():
            store.add_event(ev)
    html_out = tmp_path / "r.html"
    csv_out = tmp_path / "r.csv"
    rc = report_main(
        [
            "--db",
            str(db),
            "--out",
            str(html_out),
            "--csv",
            str(csv_out),
            "--generated-at",
            "2026-01-01 UTC",
        ]
    )
    assert rc == 0
    assert csv_out.exists()
    assert len(csv_out.read_text().splitlines()) == 3
    assert "rows" in capsys.readouterr().out
