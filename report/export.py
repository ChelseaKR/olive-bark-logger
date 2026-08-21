"""CSV export of the event log, for spreadsheets or handing to property management.

Pure stdlib `csv`. Times are written both as unix seconds and as an ISO-8601 string in
the report's time zone, so the file is usable without re-deriving local time. Each row
also records the calibration offset included in its levels (0.0 = raw dBFS), so the
export is self-describing about its calibration state: raw = value - offset.

Like every other export path, the "what this can and cannot prove" cover block is written
as a leading ``#`` comment preamble so the caveat travels with the file. This one is
handed to property management as readily as the quiet-hours export is, and it shipped
without the block until the export gate started enumerating paths rather than naming them.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING

from monitor.detector import Event

from report.render import CALIBRATION_NONE, CALIBRATION_UNSTATED, cover_text_lines

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
    "calibration_basis",
    "monitored",
    "rise_time_s",
    "loud6_s",
    "longest_run_s",
    "coarse_tag",
]


def resolve_basis(
    basis: Sequence[str] | None, offsets_db: Sequence[float] | None, n: int
) -> list[str]:
    """The per-row calibration basis an export writes, never guessed.

    Given, it must parallel the rows. Absent with no offsets, every row is raw
    (`none`). Absent with offsets present, the export cannot know whether each offset
    was in force or back-applied, and says `unstated` rather than inventing an answer.
    """
    if basis is not None:
        out = list(basis)
        if len(out) != n:
            raise ValueError("basis must have one entry per event")
        return out
    return [CALIBRATION_NONE if offsets_db is None else CALIBRATION_UNSTATED] * n


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
    basis: Sequence[str] | None = None,
    gaps: list[Gap] | None = None,
) -> int:
    """Write events to a CSV file. Returns the number of rows written.

    `offsets_db`, when given, must parallel `events` and record the calibration offset
    already applied (at render time) to each event's peak/avg levels. Omitted means the
    levels are raw, uncalibrated dBFS (offset 0.0).

    `basis` parallels `offsets_db` and says, per row, whether that offset was in force
    when the row was measured (`in-force`), back-applied from a calibration taken later
    (`back-applied`), the deprecated config bootstrap (`bootstrap-config`), or absent
    (`none`) — see `report.render.CALIBRATION_*`. A row measured nineteen days before
    the microphone was ever calibrated carries the same `+48.0` as one measured after,
    and without this column nothing in the file distinguishes them. Omitted with
    offsets present, the column reads `unstated` rather than guessing; omitted with no
    offsets, every row is `none`.

    The `monitored` column is "yes" unless the event overlaps a recorded monitoring gap
    (the device was not listening), so an event logged at the edge of an outage is flagged.

    The R1 cover block leads the file as ``#`` comments; the machine-readable rows below
    it are unchanged, and every csv reader in common use skips comment lines.
    """
    offs = list(offsets_db) if offsets_db is not None else [0.0] * len(events)
    if len(offs) != len(events):
        raise ValueError("offsets_db must have one entry per event")
    bases = resolve_basis(basis, offsets_db, len(events))
    gap_list = gaps or []
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        for line in cover_text_lines():
            fh.write(f"# {line}\n" if line else "#\n")
        writer = csv.writer(fh)
        writer.writerow(_HEADER)
        for ev, off, how in zip(events, offs, bases):
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
                    how,
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
