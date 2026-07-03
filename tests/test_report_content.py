"""Merge-blocking: the report carries methodology + limitations and honest framing."""

from __future__ import annotations

from datetime import datetime, timezone

from monitor.config import Config
from monitor.detector import Event
from report.aggregate import summarize
from report.render import (
    LIMITATIONS_HEADING,
    METHODOLOGY_HEADING,
    NO_SOURCE_NOTE,
    PARAM_CHANGE_NOTE,
    RELATIVE_DBFS_NOTE,
    build_report,
    generate_report_from_db,
)


def _report(events=None, **cfg):
    config = Config(**cfg)
    summary = summarize(events or [], quiet_hours=config.quiet_hours, tz=config.tzinfo())
    return build_report(summary, config=config, generated_at="2026-01-01 00:00 UTC")


def test_has_methodology_and_limitations_headings():
    html = _report()
    assert f"<h2>{METHODOLOGY_HEADING}</h2>" in html
    assert f"<h2>{LIMITATIONS_HEADING}</h2>" in html


def test_states_relative_dbfs_limitation():
    html = _report()
    assert RELATIVE_DBFS_NOTE in html
    assert "relative" in html.lower() and "dbfs" in html.lower()


def test_states_no_source_attribution():
    html = _report()
    assert NO_SOURCE_NOTE in html
    assert "cannot prove" in html.lower()


def test_states_no_audio_recorded():
    html = _report()
    assert "No audio was recorded" in html


def test_uncalibrated_is_disclosed():
    html = _report(calibration_offset=0.0)
    assert "No calibration offset is applied" in html


def test_calibrated_offset_is_disclosed():
    html = _report(calibration_offset=12.5)
    assert "+12.5 dB" in html


def test_reports_event_numbers():
    start = datetime(2026, 1, 1, 23, tzinfo=timezone.utc).timestamp()
    ev = Event(start=start, end=start + 5, duration=5.0, peak_level=-8.0, avg_level=-12.0)
    html = _report([ev])
    assert "Total events" in html
    assert ">1<" in html  # the count appears


def test_measurement_conditions_without_session():
    html = _report()
    assert "<h2>Measurement conditions</h2>" in html
    assert "were not recorded" in html


def test_measurement_conditions_with_session():
    from store import Session

    session = Session(
        id=1,
        started_at=0.0,
        ended_at=1.0,
        device_label="pi-1",
        mic_model="USB mic",
        placement_note="by the wall",
        tz="UTC",
        calibration_offset=0.0,
        calibration_note="x",
        frames_seen=990,
        frames_dropped=10,
        app_version="0.1.0",
    )
    config = Config()
    summary = summarize([], quiet_hours=config.quiet_hours, tz=config.tzinfo())
    html = build_report(
        summary, config=config, generated_at="2026-01-01 00:00 UTC", session=session
    )
    assert "pi-1" in html and "USB mic" in html and "by the wall" in html
    assert "99.0%" in html  # frame coverage


def test_event_types_section_appears_with_tags():
    base = datetime(2026, 1, 1, 12, tzinfo=timezone.utc).timestamp()
    events = [
        Event(base, base + 2, 2.0, -8, -12, coarse_tag="bark-like"),
        Event(base + 10, base + 11, 1.0, -9, -13, coarse_tag="ambient"),
        Event(base + 20, base + 22, 2.0, -7, -11, coarse_tag="bark-like"),
    ]
    html = _report(events)
    assert "<h2>Event types (coarse hint)</h2>" in html
    assert "bark-like" in html and "ambient" in html
    assert "hint, not a fact" in html


def test_event_types_section_absent_without_tags():
    base = datetime(2026, 1, 1, 12, tzinfo=timezone.utc).timestamp()
    html = _report([Event(base, base + 2, 2.0, -8, -12)])
    assert "Event types" not in html


def _session(sid, started_at, **params):
    from store import Session

    return Session(
        id=sid,
        started_at=started_at,
        ended_at=started_at + 100,
        device_label="pi-1",
        mic_model="USB mic",
        placement_note="by the wall",
        tz="UTC",
        calibration_offset=0.0,
        calibration_note="x",
        frames_seen=100,
        frames_dropped=0,
        app_version="0.1.0",
        **params,
    )


def test_single_session_shows_no_parameter_epochs_table():
    session = _session(1, 0.0, threshold_dbfs=-35.0, min_duration_s=0.4, debounce_s=1.0)
    config = Config()
    summary = summarize([], quiet_hours=config.quiet_hours, tz=config.tzinfo())
    html = build_report(
        summary,
        config=config,
        generated_at="2026-01-01 00:00 UTC",
        session=session,
        sessions=[session],
    )
    assert "Detection-parameter epochs" not in html
    assert PARAM_CHANGE_NOTE not in html


def test_two_sessions_with_different_thresholds_render_epochs(tmp_path):
    from monitor.detector import Event
    from store import EventStore

    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        common = dict(
            device_label="pi-1",
            mic_model="USB mic",
            placement_note="by the wall",
            tz="UTC",
            calibration_offset=0.0,
            calibration_note="x",
            app_version="0.1.0",
            min_duration_s=0.4,
            debounce_s=1.0,
            sample_rate=16000,
            frame_size=1600,
        )
        base = datetime(2026, 1, 1, 12, tzinfo=timezone.utc).timestamp()
        s1 = store.start_session(started_at=base, threshold_dbfs=-35.0, **common)
        store.add_event(Event(base + 1, base + 3, 2.0, -8, -12), session_id=s1)
        later = datetime(2026, 1, 5, 12, tzinfo=timezone.utc).timestamp()
        s2 = store.start_session(started_at=later, threshold_dbfs=-42.0, **common)
        store.add_event(Event(later + 1, later + 3, 2.0, -20, -24), session_id=s2)

    html = generate_report_from_db(str(db), Config(tz="UTC"), generated_at="2026-01-06 00:00 UTC")
    assert "Detection-parameter epochs" in html
    assert PARAM_CHANGE_NOTE in html
    # Both thresholds in force during the record are named.
    assert "-35 dBFS" in html
    assert "-42 dBFS" in html
    # Each epoch is dated by its first session's start.
    assert "2026-01-01" in html and "2026-01-05" in html


def test_fmt_seconds_minutes_and_hours():
    # Exercise the minute/hour formatting branches via long durations.
    base = datetime(2026, 1, 1, 12, tzinfo=timezone.utc).timestamp()
    long_event = Event(start=base, end=base + 4000, duration=4000.0, peak_level=-5, avg_level=-9)
    html = _report([long_event])
    assert " h" in html  # 4000 s renders in hours
