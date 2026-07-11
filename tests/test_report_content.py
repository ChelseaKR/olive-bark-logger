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
    RELATIVE_DBFS_NOTE,
    build_report,
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


def test_fmt_seconds_minutes_and_hours():
    # Exercise the minute/hour formatting branches via long durations.
    base = datetime(2026, 1, 1, 12, tzinfo=timezone.utc).timestamp()
    long_event = Event(start=base, end=base + 4000, duration=4000.0, peak_level=-5, avg_level=-9)
    html = _report([long_event])
    assert " h" in html  # 4000 s renders in hours


# --- R1: "what this can and cannot prove" cover page -------------------------
def test_cover_page_present_and_states_limits():
    html = _report()
    assert "<h2>What this can and cannot prove</h2>" in html
    assert 'class="cover"' in html
    assert "What it can show" in html and "What it cannot prove" in html
    # The cover restates the headline limitations in lay terms.
    assert "no source attribution" in html
    assert "not the units an ordinance" in html
    assert "is not the same as a violation" in html
    assert "not legal advice" in html


# --- R2: calibration-honesty banner + provenance ----------------------------
def test_uncalibrated_banner_is_prominent():
    html = _report(calibration_offset=0.0)
    assert 'class="banner"' in html
    assert "Uncalibrated — these readings are relative, not dB(A)." in html
    assert 'role="note"' in html


def test_calibrated_banner_shows_provenance():
    html = _report(
        calibration_offset=12.5,
        calibration_note="Ref: Brand X, IEC 61672 Class 2",
    )
    assert "banner-ok" in html
    assert "+12.5 dB" in html
    assert "Brand X, IEC 61672 Class 2" in html


# --- R3: quiet-hours duration rollup (no verdict) ---------------------------
def test_duration_rollup_reports_minutes_without_a_verdict():
    base = datetime(2026, 1, 1, 23, tzinfo=timezone.utc).timestamp()
    ev = Event(start=base, end=base + 120, duration=120.0, peak_level=-8.0, avg_level=-12.0)
    html = _report([ev])  # 23:00 is within the default 22:00-08:00 window
    assert "<h2>Quiet-hours duration rollup</h2>" in html
    assert "Loud time within quiet hours, per day" in html
    # The no-verdict line is mandatory and must be present verbatim in spirit.
    assert "This is a measurement, not a determination" in html
    assert "is not the same as a violation" in html
    # Ordinance reference framing is hedged as jurisdiction-dependent.
    assert "vary by jurisdiction" in html


def test_duration_rollup_empty_when_no_quiet_hours_events():
    base = datetime(2026, 1, 1, 12, tzinfo=timezone.utc).timestamp()
    ev = Event(start=base, end=base + 5, duration=5.0, peak_level=-8.0, avg_level=-12.0)
    html = _report([ev])  # noon -> outside the quiet window
    assert "<h2>Quiet-hours duration rollup</h2>" in html
    assert "nothing to roll up" in html


# --- R5: reader-facing no-audio rationale -----------------------------------
def test_reader_facing_no_audio_rationale_present():
    html = _report()
    assert "<h2>Why there is deliberately no audio</h2>" in html
    assert "deliberate privacy choice, not missing data" in html
    assert "leaked, subpoenaed, or misused" in html
