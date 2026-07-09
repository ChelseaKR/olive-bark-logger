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

from monitor.detector import Event

_HEADER = [
    "start_unix",
    "start_iso",
    "end_iso",
    "duration_s",
    "peak_dbfs",
    "avg_dbfs",
    "calibration_offset_db",
    "coarse_tag",
]


def events_to_csv(
    events: list[Event],
    path: str | Path,
    *,
    tz: tzinfo = timezone.utc,
    offsets_db: Sequence[float] | None = None,
) -> int:
    """Write events to a CSV file. Returns the number of rows written.

    `offsets_db`, when given, must parallel `events` and record the calibration offset
    already applied (at render time) to each event's peak/avg levels. Omitted means the
    levels are raw, uncalibrated dBFS (offset 0.0).
    """
    offs = list(offsets_db) if offsets_db is not None else [0.0] * len(events)
    if len(offs) != len(events):
        raise ValueError("offsets_db must have one entry per event")
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADER)
        for ev, off in zip(events, offs):
            writer.writerow(
                [
                    f"{ev.start:.3f}",
                    datetime.fromtimestamp(ev.start, tz=tz).isoformat(),
                    datetime.fromtimestamp(ev.end, tz=tz).isoformat(),
                    f"{ev.duration:.3f}",
                    f"{ev.peak_level:.1f}",
                    f"{ev.avg_level:.1f}",
                    f"{off:+.1f}",
                    ev.coarse_tag or "",
                ]
            )
    return len(events)
