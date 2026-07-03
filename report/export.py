"""CSV export of the event log, for spreadsheets or handing to property management.

Pure stdlib `csv`. Times are written both as unix seconds and as an ISO-8601 string in
the report's time zone, so the file is usable without re-deriving local time.
"""

from __future__ import annotations

import csv
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
    "monitored",
    "coarse_tag",
]


def _is_monitored(start: float, end: float, gaps: list[Gap]) -> bool:
    """True unless the interval [start, end) overlaps any recorded monitoring gap."""
    return not any(g.start < end and g.end > start for g in gaps)


def events_to_csv(
    events: list[Event],
    path: str | Path,
    *,
    tz: tzinfo = timezone.utc,
    gaps: list[Gap] | None = None,
) -> int:
    """Write events to a CSV file. Returns the number of rows written.

    The `monitored` column is "yes" unless the event overlaps a recorded monitoring gap
    (the device was not listening), so an event logged at the edge of an outage is flagged.
    """
    gap_list = gaps or []
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADER)
        for ev in events:
            monitored = _is_monitored(ev.start, ev.end, gap_list)
            writer.writerow(
                [
                    f"{ev.start:.3f}",
                    datetime.fromtimestamp(ev.start, tz=tz).isoformat(),
                    datetime.fromtimestamp(ev.end, tz=tz).isoformat(),
                    f"{ev.duration:.3f}",
                    f"{ev.peak_level:.1f}",
                    f"{ev.avg_level:.1f}",
                    "yes" if monitored else "no",
                    ev.coarse_tag or "",
                ]
            )
    return len(events)
