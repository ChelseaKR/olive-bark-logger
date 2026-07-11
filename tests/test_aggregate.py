"""Aggregation: counts, distributions, and quiet-hours figures."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from monitor.config import QuietHours
from monitor.detector import Event
from report.aggregate import summarize


def _ev(hour: int, day: int = 1, duration: float = 2.0, peak: float = -10.0) -> Event:
    start = datetime(2026, 1, day, hour, 0, tzinfo=timezone.utc).timestamp()
    return Event(
        start=start, end=start + duration, duration=duration, peak_level=peak, avg_level=peak - 3
    )


def test_empty_summary():
    s = summarize([], quiet_hours=QuietHours())
    assert s.event_count == 0
    assert s.by_hour == {h: 0 for h in range(24)}
    assert s.by_day == {}


def test_counts_and_distributions():
    events = [_ev(23), _ev(23), _ev(12, day=2)]
    s = summarize(events, quiet_hours=QuietHours(22, 8))
    assert s.event_count == 3
    assert s.by_hour[23] == 2
    assert s.by_hour[12] == 1
    assert s.by_day == {"2026-01-01": 2, "2026-01-02": 1}


def test_quiet_hours_breakdown():
    events = [_ev(23), _ev(2), _ev(12)]  # two in quiet window (22-8), one out
    s = summarize(events, quiet_hours=QuietHours(22, 8))
    assert s.quiet_hours_event_count == 2
    assert s.quiet_hours_loud_seconds == 4.0


def test_quiet_hours_duration_rollup_per_day():
    # R3: accumulated loud time within the quiet-hours window, totaled per day. Events
    # outside the window (12:00) never contribute; attribution is by event start day.
    events = [
        _ev(23, day=1, duration=5.0),  # day 1, within window
        _ev(2, day=1, duration=3.0),  # day 1, within window (early morning of the 1st)
        _ev(12, day=1, duration=9.0),  # outside window -> excluded
        _ev(23, day=2, duration=4.0),  # day 2, within window
    ]
    s = summarize(events, quiet_hours=QuietHours(22, 8))
    assert s.quiet_hours_loud_seconds_by_day == {"2026-01-01": 8.0, "2026-01-02": 4.0}
    # The rollup never exceeds the total quiet-hours loud time.
    assert sum(s.quiet_hours_loud_seconds_by_day.values()) == s.quiet_hours_loud_seconds


def test_quiet_hours_duration_rollup_empty_when_none_in_window():
    s = summarize([_ev(12), _ev(14)], quiet_hours=QuietHours(22, 8))
    assert s.quiet_hours_loud_seconds_by_day == {}


def test_peak_stats():
    events = [_ev(1, peak=-20), _ev(2, peak=-5), _ev(3, peak=-15)]
    s = summarize(events, quiet_hours=QuietHours())
    assert s.loudest_peak_dbfs == -5
    assert abs(s.mean_peak_dbfs - ((-20 + -5 + -15) / 3)) < 1e-9
    assert s.longest_event_seconds == 2.0


def test_fixed_offset_shifts_buckets():
    # An event at 23:00 UTC lands in hour 1 the next day at a +2h zone.
    events = [_ev(23)]
    s = summarize(events, quiet_hours=QuietHours(), tz=timezone(timedelta(hours=2)))
    assert s.by_hour[1] == 1


def test_dst_aware_bucketing():
    """Two events at the same local wall-clock hour bucket together across a DST change.

    A fixed UTC offset would mis-bucket one of them by an hour; an IANA zone does not.
    """
    zi = pytest.importorskip("zoneinfo")
    try:
        la = zi.ZoneInfo("America/Los_Angeles")  # PST (UTC-8) winter, PDT (UTC-7) summer
    except zi.ZoneInfoNotFoundError:  # pragma: no cover - host without tzdata
        pytest.skip("tzdata not available")

    winter = datetime(2026, 1, 15, 23, 30, tzinfo=la).timestamp()  # PST
    summer = datetime(2026, 7, 15, 23, 30, tzinfo=la).timestamp()  # PDT
    events = [
        Event(winter, winter + 1, 1.0, -10, -13),
        Event(summer, summer + 1, 1.0, -10, -13),
    ]
    s = summarize(events, quiet_hours=QuietHours(22, 8), tz=la)
    assert s.by_hour[23] == 2  # both at local 23:30 despite the offset change
    assert s.quiet_hours_event_count == 2
