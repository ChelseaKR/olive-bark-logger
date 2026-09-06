"""Summarize a list of events into the numbers the report shows.

All time bucketing uses an explicit time zone (an IANA zone from config), so daily and
hourly distributions and quiet-hours compliance stay correct across daylight-saving
transitions, and the same event log + zone always produces the same report.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import TYPE_CHECKING

from monitor.ambient import percentile
from monitor.config import QuietSchedule
from monitor.detector import Event
from monitor.drift import DriftAdvisory

if TYPE_CHECKING:
    from store import ClockAnomaly, DriftAdvisoryRecord, MinuteLevel


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


@dataclass(frozen=True)
class AmbientDay:
    """One day's ambient baseline (EXP-01), rolled up from per-minute summaries.

    `min_dbfs`/`max_dbfs` are exact (the extrema of the day's per-minute extrema).
    `median_dbfs`/`l90_dbfs` are *approximations*: computed across the day's per-minute
    median/L90 values rather than re-derived from raw samples, which no longer exist
    past the minute they summarized. The renderer discloses this explicitly.
    """

    day: str  # ISO date, in the report's configured time zone
    min_dbfs: float
    median_dbfs: float
    max_dbfs: float
    l90_dbfs: float
    minutes_covered: int


# The percentile rank used to roll per-minute L90 values up to a day figure -- the same
# "exceeded 90% of the time" rule described in monitor/ambient.py, applied one level up.
_DAY_L90_PERCENTILE_RANK = 10.0


def summarize_ambient(
    minute_levels: list[MinuteLevel], *, tz: tzinfo = timezone.utc
) -> list[AmbientDay]:
    """Roll up per-minute ambient summaries (EXP-01) into one row per calendar day.

    Empty input yields an empty list, exactly like `summarize`'s `by_day` for events --
    the ambient section is omitted entirely by the renderer when there is nothing to
    show (the feature is opt-in and off by default).
    """
    by_day: dict[str, list[MinuteLevel]] = {}
    for m in minute_levels:
        day = datetime.fromtimestamp(m.minute_start, tz=tz).date().isoformat()
        by_day.setdefault(day, []).append(m)

    days: list[AmbientDay] = []
    for day, minutes in sorted(by_day.items()):
        medians = sorted(m.median_dbfs for m in minutes)
        l90s = sorted(m.l90_dbfs for m in minutes)
        days.append(
            AmbientDay(
                day=day,
                min_dbfs=min(m.min_dbfs for m in minutes),
                median_dbfs=statistics.median(medians),
                max_dbfs=max(m.max_dbfs for m in minutes),
                l90_dbfs=percentile(l90s, _DAY_L90_PERCENTILE_RANK),
                minutes_covered=len(minutes),
            )
        )
    return days


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


DRIFT_STEADY_NOTE = (
    "Drift watch: the ambient baseline has not moved more than the configured tolerance "
    "since the current calibration. Levels here mean the same thing they meant when the "
    "device was calibrated."
)

DRIFT_UNAVAILABLE_PREFIX = "Drift watch unavailable: "

DRIFT_UNAVAILABLE_NOTE = (
    "An unavailable drift watch is not a steady one. Nothing below has been checked "
    "against the calibration epoch, so this report cannot say whether the microphone "
    "has moved."
)


def describe_drift_advisories(
    advisories: list[DriftAdvisoryRecord], *, tz: tzinfo = timezone.utc
) -> list[str]:
    """Plain-language disclosure lines for recorded drift advisories, wall times in `tz`.

    Empty input yields an empty list. The renderer must not read that as "steady": an
    advisory is only written when a comparison ran *and* tripped, so no rows can also
    mean no comparison ever ran. The renderer pairs this with the availability state.
    """
    return [describe_drift_advisory(a, tz=tz) for a in advisories]


def describe_drift_advisory(
    advisory: DriftAdvisoryRecord | DriftAdvisory, *, tz: tzinfo = timezone.utc
) -> str:
    """One advisory as a sentence an operator can act on."""
    calibrated = datetime.fromtimestamp(advisory.calibration_epoch, tz=tz).strftime("%Y-%m-%d")
    delta = advisory.largest_delta_db
    direction = "up" if delta > 0 else "down"
    return (
        f"Ambient baseline moved {delta:+.1f} dB ({direction}) since calibration on "
        f"{calibrated}; the microphone may have moved or drifted — re-run "
        f"`olive-calibrate`. Median {advisory.median_delta_db:+.1f} dB, L90 "
        f"{advisory.l90_delta_db:+.1f} dB, tolerance {advisory.tolerance_db:.1f} dB, "
        f"over {advisory.reference_minutes} reference and {advisory.recent_minutes} "
        f"recent ambient minutes. This is advisory: no detection parameter was changed."
    )


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
