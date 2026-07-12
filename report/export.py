"""CSV export of the event log, for spreadsheets or handing to property management.

Pure stdlib `csv`. Times are written both as unix seconds and as an ISO-8601 string in
the report's time zone, so the file is usable without re-deriving local time. Each row
also records the calibration offset included in its levels (0.0 = raw dBFS), so the
export is self-describing about its calibration state: raw = value - offset.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING

from monitor.detector import Event

if TYPE_CHECKING:
    from store import Gap

_HEADER = [
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


def _is_monitored(start: float, end: float, gaps: list[Gap]) -> bool:
    """True unless the interval [start, end) overlaps any recorded monitoring gap."""
    return not any(g.start < end and g.end > start for g in gaps)


def _sec(value: float | None) -> str:
    """One-decimal seconds, or blank for a missing (legacy) anatomy value."""
    return "" if value is None else f"{value:.1f}"


def events_to_csv(
    events: list[Event],
    path: str | Path,
    *,
    tz: tzinfo = timezone.utc,
    offsets_db: Sequence[float] | None = None,
    gaps: list[Gap] | None = None,
) -> int:
    """Write events to a CSV file. Returns the number of rows written.

    `offsets_db`, when given, must parallel `events` and record the calibration offset
    already applied (at render time) to each event's peak/avg levels. Omitted means the
    levels are raw, uncalibrated dBFS (offset 0.0).

    The `monitored` column is "yes" unless the event overlaps a recorded monitoring gap
    (the device was not listening), so an event logged at the edge of an outage is flagged.
    """
    offs = list(offsets_db) if offsets_db is not None else [0.0] * len(events)
    if len(offs) != len(events):
        raise ValueError("offsets_db must have one entry per event")
    gap_list = gaps or []
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADER)
        for ev, off in zip(events, offs):
            monitored = _is_monitored(ev.start, ev.end, gap_list)
            writer.writerow(
                [
                    f"{ev.start:.3f}",
                    datetime.fromtimestamp(ev.start, tz=tz).isoformat(),
                    datetime.fromtimestamp(ev.end, tz=tz).isoformat(),
                    f"{ev.duration:.3f}",
                    f"{ev.peak_level:.1f}",
                    f"{ev.avg_level:.1f}",
                    f"{off:+.1f}",
                    "yes" if monitored else "no",
                    # Envelope anatomy is independent of coarse_tag: it is emitted even
                    # when the (opt-in) tag is suppressed, since it carries no hint about
                    # the sound's source — only its shape.
                    _sec(ev.rise_time_s),
                    _sec(ev.loud6_s),
                    _sec(ev.longest_run_s),
                    ev.coarse_tag or "",
                ]
            )
    return len(events)
