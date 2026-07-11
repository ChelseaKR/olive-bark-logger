"""Summarize a list of events into the numbers the report shows.

All time bucketing uses an explicit time zone (an IANA zone from config), so daily and
hourly distributions and quiet-hours compliance stay correct across daylight-saving
transitions, and the same event log + zone always produces the same report.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import TYPE_CHECKING

from monitor.config import QuietSchedule
from monitor.detector import Event

if TYPE_CHECKING:
    from store import ClockAnomaly


@dataclass(frozen=True)
class Summary:
    event_count: int
    total_loud_seconds: float
    longest_event_seconds: float
    loudest_peak_dbfs: float
    mean_peak_dbfs: float
    by_hour: dict[int, int] = field(default_factory=dict)  # hour-of-day 0..23 -> count
    by_day: dict[str, int] = field(default_factory=dict)  # ISO date -> count
    by_tag: dict[str, int] = field(default_factory=dict)  # coarse tag -> count (if tagging on)
    # ISO date -> {hour-of-day 0..23 -> count}: the day x hour grid the calendar heatmap
    # draws. Metadata only (counts of level-events), never audio — same guarantee as the
    # rest of the summary.
    by_day_hour: dict[str, dict[int, int]] = field(default_factory=dict)
    quiet_hours_event_count: int = 0
    # Pro-rated: only the portion of each event's duration that actually falls inside the
    # quiet-hours window, split across the boundary (see QuietHours.overlap_seconds).
    quiet_hours_loud_seconds: float = 0.0
    # The previous, start-attributed figure (whole duration counted if the event *started*
    # in quiet hours). Retained alongside the pro-rated number during the transition so a
    # reader can see both and reconcile them.
    quiet_hours_loud_seconds_start_attributed: float = 0.0
    # ISO date -> seconds of detected loud time within the quiet-hours window on that day
    # (attributed by each event's start time). Feeds the ordinance/CC&R duration rollup;
    # it reports accumulated duration, never a violation verdict.
    quiet_hours_loud_seconds_by_day: dict[str, float] = field(default_factory=dict)


def describe_clock_anomalies(
    anomalies: list[ClockAnomaly], *, tz: tzinfo = timezone.utc
) -> list[str]:
    """Plain-language disclosure lines for detected clock jumps, wall times in `tz`.

    Empty input yields an empty list; the renderer turns that into an explicit
    "no anomalies" reassurance so the absence of jumps is stated, not merely implied.
    """
    lines: list[str] = []
    for a in anomalies:
        before = datetime.fromtimestamp(a.wall_before, tz=tz).strftime("%Y-%m-%d %H:%M:%S")
        after = datetime.fromtimestamp(a.wall_after, tz=tz).strftime("%Y-%m-%d %H:%M:%S")
        direction = "forward" if a.delta > 0 else "backward"
        lines.append(
            f"Clock jumped {direction} by {abs(a.delta):.1f} s (wall time {before} → {after})."
        )
    return lines


def summarize(
    events: list[Event],
    *,
    quiet_hours: QuietSchedule,
    tz: tzinfo = timezone.utc,
) -> Summary:
    """Reduce events to distributions and quiet-hours compliance figures."""
    if not events:
        return Summary(
            event_count=0,
            total_loud_seconds=0.0,
            longest_event_seconds=0.0,
            loudest_peak_dbfs=0.0,
            mean_peak_dbfs=0.0,
            by_hour={h: 0 for h in range(24)},
            by_day={},
        )

    by_hour: Counter[int] = Counter()
    by_day: Counter[str] = Counter()
    by_tag: Counter[str] = Counter()
    by_day_hour: dict[str, Counter[int]] = {}
    quiet_count = 0
    quiet_seconds = 0.0
    quiet_seconds_start_attributed = 0.0
    quiet_seconds_by_day: dict[str, float] = {}
    total_seconds = 0.0
    peaks: list[float] = []

    for ev in events:
        dt = datetime.fromtimestamp(ev.start, tz=tz)
        day = dt.date().isoformat()
        by_hour[dt.hour] += 1
        by_day[day] += 1
        by_day_hour.setdefault(day, Counter())[dt.hour] += 1
        if ev.coarse_tag:
            by_tag[ev.coarse_tag] += 1
        total_seconds += ev.duration
        peaks.append(ev.peak_level)
        # Counts stay start-attributed (a count cannot be fractional); loud seconds are
        # pro-rated across the quiet-window boundary.
        end_dt = datetime.fromtimestamp(ev.start + ev.duration, tz=tz)
        quiet_seconds += quiet_hours.overlap_seconds(dt, end_dt)
        if quiet_hours.contains(dt):
            quiet_count += 1
            quiet_seconds_start_attributed += ev.duration
            quiet_seconds_by_day[day] = quiet_seconds_by_day.get(day, 0.0) + ev.duration

    return Summary(
        event_count=len(events),
        total_loud_seconds=total_seconds,
        longest_event_seconds=max(ev.duration for ev in events),
        loudest_peak_dbfs=max(peaks),
        mean_peak_dbfs=sum(peaks) / len(peaks),
        by_hour={h: by_hour.get(h, 0) for h in range(24)},
        by_day=dict(sorted(by_day.items())),
        by_tag=dict(sorted(by_tag.items())),
        by_day_hour={
            day: {h: counts.get(h, 0) for h in range(24)}
            for day, counts in sorted(by_day_hour.items())
        },
        quiet_hours_event_count=quiet_count,
        quiet_hours_loud_seconds=quiet_seconds,
        quiet_hours_loud_seconds_start_attributed=quiet_seconds_start_attributed,
        quiet_hours_loud_seconds_by_day=dict(sorted(quiet_seconds_by_day.items())),
    )
