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


def _ev_at(dt: datetime, duration: float) -> Event:
    start = dt.timestamp()
    return Event(
        start=start, end=start + duration, duration=duration, peak_level=-10, avg_level=-13
    )


def test_overlap_seconds_prorates_boundary():
    # 120 s event straddling the 22:00 quiet-hours start contributes exactly 60 s.
    qh = QuietHours(22, 8)
    start = datetime(2026, 1, 1, 21, 59, 0, tzinfo=timezone.utc)
    end = start + timedelta(seconds=120)
    assert qh.overlap_seconds(start, end) == 60.0


def test_overlap_seconds_fully_inside_and_outside():
    qh = QuietHours(22, 8)
    inside_s = datetime(2026, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
    assert qh.overlap_seconds(inside_s, inside_s + timedelta(seconds=45)) == 45.0
    outside_s = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # long but wholly outside
    assert qh.overlap_seconds(outside_s, outside_s + timedelta(hours=2)) == 0.0


def test_overlap_seconds_midnight_wrap():
    qh = QuietHours(22, 8)
    start = datetime(2026, 1, 1, 23, 59, 30, tzinfo=timezone.utc)  # crosses midnight
    assert qh.overlap_seconds(start, start + timedelta(seconds=60)) == 60.0


def test_overlap_seconds_partition_invariant():
    # For any event, the pro-rated quiet seconds are within [0, duration], and the quiet
    # portion plus the non-quiet portion equal the whole duration (a clean partition).
    qh = QuietHours(22, 8)
    starts = [datetime(2026, 1, 1, h, m, tzinfo=timezone.utc) for h in range(24) for m in (0, 37)]
    complement = QuietHours(8, 22)  # the complementary daily window (8:00 -> 22:00)
    for s in starts:
        for dur in (5.0, 90.0, 3600.0, 7200.0):
            e = s + timedelta(seconds=dur)
            quiet = qh.overlap_seconds(s, e)
            nonquiet = complement.overlap_seconds(s, e)
            assert 0.0 <= quiet <= dur + 1e-9
            assert abs(quiet + nonquiet - dur) < 1e-6


def test_overlap_seconds_overlapping_windows_count_once():
    # The schedule is a union: an instant covered by two windows is one quiet second,
    # never two. 22:00-08:00 daily and 23:00-01:00 daily overlap 23:00-01:00 entirely.
    from monitor.config import QuietSchedule, QuietWindow

    sched = QuietSchedule(
        (
            QuietWindow(start_minute=22 * 60, end_minute=8 * 60),
            QuietWindow(start_minute=23 * 60, end_minute=1 * 60),
        )
    )
    start = datetime(2026, 1, 1, 22, 30, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=3)  # 22:30 -> 01:30, all inside the union
    assert sched.overlap_seconds(start, end) == 3 * 3600.0


def test_overlap_seconds_day_restricted_window():
    # A Fri-only 23:00->07:00 window covers early Saturday because it STARTED on Friday,
    # and covers nothing on other weekdays. 2026-01-02 is a Friday.
    from monitor.config import QuietSchedule, QuietWindow

    sched = QuietSchedule(
        (QuietWindow(start_minute=23 * 60, end_minute=7 * 60, days=frozenset({4})),)
    )
    fri_night = datetime(2026, 1, 2, 23, 30, 0, tzinfo=timezone.utc)
    assert sched.overlap_seconds(fri_night, fri_night + timedelta(hours=1)) == 3600.0
    sat_early = datetime(2026, 1, 3, 6, 0, 0, tzinfo=timezone.utc)  # tail of Fri window
    assert sched.overlap_seconds(sat_early, sat_early + timedelta(hours=2)) == 3600.0
    tue_night = datetime(2026, 1, 6, 23, 30, 0, tzinfo=timezone.utc)  # Tuesday: inactive
    assert sched.overlap_seconds(tue_night, tue_night + timedelta(hours=1)) == 0.0


def test_summary_reports_both_prorated_and_start_attributed():
    qh = QuietHours(22, 8)
    # 120 s event straddling 22:00 start: pro-rated = 60 s, but start-attributed = 0
    # (it started at 21:59, outside quiet hours, so the whole duration is credited outside).
    straddle = _ev_at(datetime(2026, 1, 1, 21, 59, 0, tzinfo=timezone.utc), 120.0)
    inside = _ev_at(datetime(2026, 1, 1, 23, 0, 0, tzinfo=timezone.utc), 40.0)
    s = summarize([straddle, inside], quiet_hours=qh)
    assert s.quiet_hours_event_count == 1  # only the 23:00 event started in quiet hours
    assert s.quiet_hours_loud_seconds == 100.0  # 60 (pro-rated straddle) + 40 (inside)
    assert s.quiet_hours_loud_seconds_start_attributed == 40.0  # whole-duration, start only


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
    # Every event here lies wholly inside the window, so the start-attributed per-day
    # rollup and the pro-rated total agree exactly.
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
