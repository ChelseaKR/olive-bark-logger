"""Summarize a list of events into the numbers the report shows.

All time bucketing uses an explicit time zone (an IANA zone from config), so daily and
hourly distributions and quiet-hours compliance stay correct across daylight-saving
transitions, and the same event log + zone always produces the same report.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo

from monitor.config import QuietSchedule
from monitor.detector import Event


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
    quiet_hours_loud_seconds: float = 0.0


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
        if quiet_hours.contains(dt):
            quiet_count += 1
            quiet_seconds += ev.duration

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
    )
