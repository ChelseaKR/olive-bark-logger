"""Quiet-hours violation analysis and honest export for a neighbor/landlord submission.

A "violation" here means strictly: a logged sound-level event whose **start time**, in the
configured local time zone, fell inside the configured quiet-hours window. That is all the
data can support — the tool measures levels, never content, so it cannot and does not claim
to prove *what* made a sound or *who* is responsible. Every export carries that limitation
in writing, consistent with docs/audits/methodology-and-limitations.md.

Like the rest of the report side this is pure stdlib (csv + datetime) and deterministic
given its inputs: the same event log, quiet-hours window, and time zone always produce the
same CSV bytes and the same HTML.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from html import escape
from pathlib import Path

from monitor.config import QuietHours
from monitor.detector import Event

from report.render import (
    _STYLE,
    NO_AUDIO_RATIONALE,
    NO_SOURCE_NOTE,
    RELATIVE_DBFS_NOTE,
    _fmt_seconds,
    cover_html,
    cover_text_lines,
)


@dataclass(frozen=True)
class ViolationRow:
    """One event classified against the quiet-hours window. Metadata only — no audio."""

    start_unix: float
    start_iso: str
    end_iso: str
    hour: int  # local hour-of-day (0..23) of the event start
    duration_s: float
    peak_dbfs: float
    avg_dbfs: float
    within_quiet_hours: bool
    coarse_tag: str | None


@dataclass(frozen=True)
class ViolationReport:
    """Counts and per-event rows for the quiet-hours analysis of an event log."""

    window: str  # e.g. "22:00–08:00"  # noqa: RUF003 - intentional en dash
    tz_name: str
    total_events: int
    within_count: int
    outside_count: int
    within_loud_seconds: float
    outside_loud_seconds: float
    rows: list[ViolationRow]


def _window_label(quiet_hours: QuietHours) -> str:
    return f"{quiet_hours.start_hour % 24:02d}:00–{quiet_hours.end_hour % 24:02d}:00"  # noqa: RUF001 - intentional en dash


def compute_violations(
    events: list[Event],
    *,
    quiet_hours: QuietHours,
    tz: tzinfo = timezone.utc,
    tz_name: str = "UTC",
) -> ViolationReport:
    """Classify every event as within / outside the quiet-hours window by its start time."""
    rows: list[ViolationRow] = []
    within = 0
    within_secs = 0.0
    outside_secs = 0.0
    for ev in events:
        dt = datetime.fromtimestamp(ev.start, tz=tz)
        is_within = quiet_hours.contains(dt)
        if is_within:
            within += 1
            within_secs += ev.duration
        else:
            outside_secs += ev.duration
        rows.append(
            ViolationRow(
                start_unix=ev.start,
                start_iso=dt.isoformat(),
                end_iso=datetime.fromtimestamp(ev.end, tz=tz).isoformat(),
                hour=dt.hour,
                duration_s=ev.duration,
                peak_dbfs=ev.peak_level,
                avg_dbfs=ev.avg_level,
                within_quiet_hours=is_within,
                coarse_tag=ev.coarse_tag,
            )
        )
    return ViolationReport(
        window=_window_label(quiet_hours),
        tz_name=tz_name,
        total_events=len(events),
        within_count=within,
        outside_count=len(events) - within,
        within_loud_seconds=within_secs,
        outside_loud_seconds=outside_secs,
        rows=rows,
    )


_CSV_HEADER = [
    "start_unix",
    "start_iso",
    "end_iso",
    "hour_local",
    "duration_s",
    "peak_dbfs",
    "avg_dbfs",
    "within_quiet_hours",
    "quiet_window",
    "coarse_tag",
]


def violations_to_csv(
    events: list[Event],
    path: str | Path,
    *,
    quiet_hours: QuietHours,
    tz: tzinfo = timezone.utc,
    tz_name: str = "UTC",
) -> int:
    """Write every event with a within/outside-quiet-hours flag. Returns rows written.

    The export is honest by construction: it lists *all* events, not only the flagged
    ones, so a reader can see the full picture rather than a cherry-picked subset. The
    "what this can and cannot prove" cover block (R1) is written as a leading ``#`` comment
    preamble so the caveat travels with the file; data rows below it are unchanged.
    """
    report = compute_violations(events, quiet_hours=quiet_hours, tz=tz, tz_name=tz_name)
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        for line in cover_text_lines():
            fh.write(f"# {line}\n" if line else "#\n")
        writer = csv.writer(fh)
        writer.writerow(_CSV_HEADER)
        for r in report.rows:
            writer.writerow(
                [
                    f"{r.start_unix:.3f}",
                    r.start_iso,
                    r.end_iso,
                    f"{r.hour:02d}",
                    f"{r.duration_s:.3f}",
                    f"{r.peak_dbfs:.1f}",
                    f"{r.avg_dbfs:.1f}",
                    "yes" if r.within_quiet_hours else "no",
                    report.window,
                    r.coarse_tag or "",
                ]
            )
    return len(report.rows)


HONEST_SCOPE_NOTE = (
    "A row marked “within quiet hours” means only that this device measured a sound level "
    "above the detection threshold, starting during the quiet-hours window. It is not proof "
    "of the source of the sound or of who caused it. Events are attributed by their start "
    "time."
)


def build_violation_report_html(
    report: ViolationReport,
    *,
    threshold_dbfs: float,
    min_duration_s: float,
    generated_at: str,
    calibrated: bool,
    title: str = "Olive's Bark Logger — Quiet-Hours Report",
) -> str:
    """Render a standalone, accessible HTML quiet-hours violation report.

    Honest posture is mandatory and unconditional: the no-source and relative-dBFS
    limitations and the scope note are always present, mirroring the main report.
    """
    if report.rows:
        body_rows = "".join(
            f'<tr><th scope="row">{escape(r.start_iso)}</th>'
            f"<td>{escape('yes' if r.within_quiet_hours else 'no')}</td>"
            f"<td>{_fmt_seconds(r.duration_s)}</td>"
            f"<td>{r.peak_dbfs:.1f}</td><td>{r.avg_dbfs:.1f}</td>"
            f"<td>{escape(r.coarse_tag or '')}</td></tr>"
            for r in report.rows
        )
        table = (
            "<table><caption>Every logged event, flagged against the quiet-hours "
            "window</caption><thead><tr>"
            '<th scope="col">Start (local)</th>'
            '<th scope="col">Within quiet hours</th>'
            '<th scope="col">Duration</th>'
            '<th scope="col">Peak (dBFS)</th>'
            '<th scope="col">Avg (dBFS)</th>'
            '<th scope="col">Coarse tag</th>'
            f"</tr></thead><tbody>{body_rows}</tbody></table>"
        )
    else:
        table = "<p>No events have been logged, so there is nothing to flag.</p>"

    calib_line = (
        "A calibration offset is applied, so levels approximate SPL but remain estimates."
        if calibrated
        else "No calibration offset is applied; levels are relative dBFS, not absolute SPL."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<a class="skip" href="#main">Skip to report</a>
<main id="main">
<h1>{escape(title)}</h1>
<p>Generated {escape(generated_at)}. This report flags logged sound-level <em>events</em>
against a configured quiet-hours window. No audio was recorded, stored, or transmitted to
produce it.</p>

{cover_html()}

<h2>Quiet-hours window</h2>
<p>Quiet hours: <strong>{escape(report.window)}</strong> in time zone
<strong>{escape(report.tz_name)}</strong> (daylight-saving aware). Configure this to match
your local ordinance, lease, or HOA rule before relying on the counts below.</p>

<h2>Summary</h2>
<dl class="stats">
<dt>Total events logged</dt><dd>{report.total_events}</dd>
<dt>Events starting within quiet hours</dt><dd>{report.within_count}</dd>
<dt>Events starting outside quiet hours</dt><dd>{report.outside_count}</dd>
<dt>Loud time within quiet hours</dt><dd>{_fmt_seconds(report.within_loud_seconds)}</dd>
<dt>Loud time outside quiet hours</dt><dd>{_fmt_seconds(report.outside_loud_seconds)}</dd>
</dl>

<h2>Events</h2>
{table}

<h2>Methodology</h2>
<p>A noise event is recorded when the measured level stays at or above
<strong>{threshold_dbfs:.0f} dBFS</strong> for at least
<strong>{min_duration_s:.1f} s</strong>. Each ~100 ms frame of audio is reduced to a single
level in memory and immediately discarded; only six numbers per event are stored — never
audio. An event counts toward quiet hours when its start time falls inside the window above.
{calib_line}</p>

<h2>Why there is deliberately no audio</h2>
<div class="note"><p>{escape(NO_AUDIO_RATIONALE)}</p></div>

<h2>Limitations</h2>
<div class="note">
<p>{escape(HONEST_SCOPE_NOTE)}</p>
<p>{escape(RELATIVE_DBFS_NOTE)}</p>
<p>{escape(NO_SOURCE_NOTE)}</p>
<p>Microphone placement and room acoustics affect every reading; these counts reflect this
device in this spot, not an absolute fact about the building. They are offered to document a
real pattern honestly, never to manufacture a case.</p>
</div>
</main>
</body>
</html>
"""
