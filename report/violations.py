"""Quiet-hours violation analysis and honest export for a neighbor/landlord submission.

A "violation" here means strictly: a logged sound-level event whose **start time**, in the
configured local time zone, fell inside the configured quiet-hours window. That is all the
data can support — the tool measures levels, never content, so it cannot and does not claim
to prove *what* made a sound or *who* is responsible. Every export carries that limitation
in writing, consistent with docs/audits/methodology-and-limitations.md.

Every export also states **how much of the window it observed**. A count is only readable
against the time it was counted over: an outage during quiet hours removes events, so a
monitor that dropped out for most of the night produces a low count that reads as a quiet
night. The coverage figures and the recorded gaps therefore travel with the counts, and
the renderer has no branch that prints counts without them.

"Observed" is measured against the capture-session ledger, not the gap ledger. A gap row
is written by a *running* monitor catching its own source failure, so the commonest
outage of all — no monitor running at all — leaves no gap behind and would otherwise be
counted as monitored time. The sessions record it as the hole between one run's end and
the next one's start, and those stretches are both subtracted and listed by date.

Like the rest of the report side this is pure stdlib (csv + datetime) and deterministic
given its inputs: the same event log, quiet-hours window, and time zone always produce the
same CSV bytes and the same HTML.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from monitor.config import QuietSchedule
from monitor.detector import Event

if TYPE_CHECKING:
    from store import Gap, Session

from report.export import resolve_basis
from report.render import (
    _STYLE,
    CALIBRATION_UNSTATED,
    NO_AUDIO_RATIONALE,
    NO_SOURCE_NOTE,
    RELATIVE_DBFS_NOTE,
    _coverage_hours,
    _coverage_window,
    _fmt_seconds,
    cover_html,
    cover_text_lines,
    off_air_spans,
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
    within_quiet_hours: bool  # start-attributed: did the event *start* in quiet hours?
    seconds_within_quiet_hours: float  # pro-rated portion of the duration inside the window
    monitored: bool  # False if the event overlaps a recorded monitoring gap
    rise_time_s: float | None  # envelope anatomy: shape descriptor, never audio
    loud6_s: float | None  # envelope anatomy: shape descriptor, never audio
    longest_run_s: float | None  # envelope anatomy: shape descriptor, never audio
    coarse_tag: str | None
    # The calibration offset already included in peak_dbfs/avg_dbfs for this row, in dB
    # (0.0 = raw, uncalibrated dBFS). Recorded so the export is self-describing:
    # raw = value - calibration_offset_db.
    calibration_offset_db: float = 0.0
    # Whether that offset was in force when this row was measured ("in-force"), applied
    # retroactively from a calibration taken later ("back-applied"), the config bootstrap
    # ("bootstrap-config"), or absent ("none"); "unstated" when the caller did not say.
    # See report.render.CALIBRATION_*. Without this, a row measured before the microphone
    # was ever calibrated is indistinguishable from one the calibration vouched for.
    calibration_basis: str = CALIBRATION_UNSTATED


@dataclass(frozen=True)
class GapWindow:
    """One recorded stretch when the device was not listening, ready for display."""

    start_iso: str
    end_iso: str
    seconds: float
    reason: str


@dataclass(frozen=True)
class ViolationReport:
    """Counts and per-event rows for the quiet-hours analysis of an event log.

    The coverage fields are not decoration: a count is only meaningful against the time
    it was counted over, so `monitored_hours` / `wall_clock_hours` travel with the counts
    and the renderer states them. Both are `None` when the record cannot support the
    figure at all (no session, no gap, no measurable event span) — that is a "cannot be
    determined", which the report says out loud rather than omitting.
    """

    window: str  # e.g. "22:00–08:00"  # noqa: RUF003 - intentional en dash
    tz_name: str
    total_events: int
    within_count: int
    outside_count: int
    within_loud_seconds: float
    outside_loud_seconds: float
    rows: list[ViolationRow]
    monitored_hours: float | None = None
    wall_clock_hours: float | None = None
    span_start_iso: str | None = None
    span_end_iso: str | None = None
    gaps: list[GapWindow] = field(default_factory=list)
    # Stretches of the span with no monitor running at all. `None` means the record
    # cannot say (a log with no capture sessions); an empty list means it can, and the
    # monitor was up throughout. The distinction is load-bearing: "we do not know" and
    # "there was none" must not render as the same sentence.
    off_air: list[GapWindow] | None = None

    @property
    def unmonitored_hours(self) -> float | None:
        """Wall-clock hours in the span the device was not listening, or None."""
        if self.monitored_hours is None or self.wall_clock_hours is None:
            return None
        return max(0.0, self.wall_clock_hours - self.monitored_hours)

    @property
    def off_air_hours(self) -> float | None:
        """Wall-clock hours in the span with no monitor running, or None if unknown."""
        if self.off_air is None:
            return None
        return sum(g.seconds for g in self.off_air) / 3600.0


def compute_violations(
    events: list[Event],
    *,
    quiet_hours: QuietSchedule,
    tz: tzinfo = timezone.utc,
    tz_name: str = "UTC",
    offsets_db: Sequence[float] | None = None,
    basis: Sequence[str] | None = None,
    gaps: list[Gap] | None = None,
    sessions: Sequence[Session] | None = None,
) -> ViolationReport:
    """Classify every event as within / outside the quiet-hours window by its start time.

    `offsets_db`, when given, must parallel `events` and record the calibration offset
    already applied (at render time) to each event's levels, so every row is
    self-describing about its calibration state. Omitted means the levels are raw (0.0).
    `basis` parallels it and says whether each offset was in force when the row was
    measured or back-applied from a later calibration (`report.export.resolve_basis`
    documents the defaults when it is omitted).

    When `gaps` is given, each row also carries a `monitored` flag (False if the event
    overlaps a monitoring gap), so a reader can tell an event logged at the edge of an
    outage from one logged with full coverage. The gaps are also carried on the report
    itself, together with the monitored-vs-wall-clock coverage figures computed by the
    same `_coverage_hours()` the main report uses (`sessions` extends the observed span
    the way it does there), so the exported document can state how much of the window it
    actually saw instead of implying it saw all of it.

    `sessions` is the *whole* capture-session ledger, not just the latest run: the
    stretches between runs are time when no monitor was listening, and no gap row can
    exist for them because writing one requires a running monitor. Passing a single
    session, or none, is still valid — the coverage figures then say only what that
    record can support.
    """
    offs = list(offsets_db) if offsets_db is not None else [0.0] * len(events)
    if len(offs) != len(events):
        raise ValueError("offsets_db must have one entry per event")
    bases = resolve_basis(basis, offsets_db, len(events))
    gap_list = gaps or []
    rows: list[ViolationRow] = []
    within = 0
    within_secs = 0.0
    outside_secs = 0.0
    for ev, off, how in zip(events, offs, bases):
        dt = datetime.fromtimestamp(ev.start, tz=tz)
        end_dt = datetime.fromtimestamp(ev.start + ev.duration, tz=tz)
        is_within = quiet_hours.contains(dt)
        quiet_secs = quiet_hours.overlap_seconds(dt, end_dt)
        if is_within:
            within += 1
        within_secs += quiet_secs
        outside_secs += ev.duration - quiet_secs
        monitored = not any(g.start < ev.end and g.end > ev.start for g in gap_list)
        rows.append(
            ViolationRow(
                start_unix=ev.start,
                start_iso=dt.isoformat(),
                end_iso=datetime.fromtimestamp(ev.end, tz=tz).isoformat(),
                hour=dt.hour,
                duration_s=ev.duration,
                peak_dbfs=ev.peak_level,
                avg_dbfs=ev.avg_level,
                rise_time_s=ev.rise_time_s,
                loud6_s=ev.loud6_s,
                longest_run_s=ev.longest_run_s,
                within_quiet_hours=is_within,
                seconds_within_quiet_hours=quiet_secs,
                monitored=monitored,
                coarse_tag=ev.coarse_tag,
                calibration_offset_db=off,
                calibration_basis=how,
            )
        )
    session_list = list(sessions) if sessions is not None else []
    coverage = _coverage_hours(events, gap_list, session_list)
    span = _coverage_window(events, gap_list, session_list)
    monitored_hours, wall_clock_hours = coverage if coverage else (None, None)
    off_air = off_air_spans(events, gap_list, session_list)
    return ViolationReport(
        window=quiet_hours.label(),
        tz_name=tz_name,
        total_events=len(events),
        within_count=within,
        outside_count=len(events) - within,
        within_loud_seconds=within_secs,
        outside_loud_seconds=outside_secs,
        rows=rows,
        monitored_hours=monitored_hours,
        wall_clock_hours=wall_clock_hours,
        span_start_iso=(datetime.fromtimestamp(span[0], tz=tz).isoformat() if span else None),
        span_end_iso=(datetime.fromtimestamp(span[1], tz=tz).isoformat() if span else None),
        gaps=[
            GapWindow(
                start_iso=datetime.fromtimestamp(g.start, tz=tz).isoformat(),
                end_iso=datetime.fromtimestamp(g.end, tz=tz).isoformat(),
                seconds=max(0.0, g.end - g.start),
                reason=g.reason,
            )
            for g in sorted(gap_list, key=lambda g: g.start)
        ],
        off_air=(
            None
            if off_air is None
            else [
                GapWindow(
                    start_iso=datetime.fromtimestamp(start, tz=tz).isoformat(),
                    end_iso=datetime.fromtimestamp(end, tz=tz).isoformat(),
                    seconds=max(0.0, end - start),
                    reason=OFF_AIR_REASON,
                )
                for start, end in off_air
            ]
        ),
    )


_CSV_HEADER = [
    "start_unix",
    "start_iso",
    "end_iso",
    "hour_local",
    "duration_s",
    "peak_dbfs",
    "avg_dbfs",
    "calibration_offset_db",
    "calibration_basis",
    "rise_time_s",
    "loud6_s",
    "longest_run_s",
    "within_quiet_hours",
    "seconds_within_quiet_hours",
    "quiet_window",
    "monitored",
    "coarse_tag",
]


def _anatomy_cell(value: float | None) -> str:
    """One-decimal seconds for an envelope descriptor, or blank on a legacy None."""
    return "" if value is None else f"{value:.1f}"


# --- Coverage: how much of the window was actually observed ------------------------
#
# A count is only meaningful against the time it was counted over. An outage during
# quiet hours removes events, so a monitor that dropped out for most of the night
# produces a low count that reads as a quiet night. These strings are mandatory on
# every quiet-hours artifact (HTML, PDF via the same HTML, and the CSV preamble); the
# honesty gate in tests/test_report_content.py asserts they cannot go missing.

COVERAGE_HEADING = "Monitoring coverage"

COVERAGE_UNKNOWN_NOTE = (
    "How much of this window the device actually monitored could not be determined from "
    "this record: it carries no monitoring session, no recorded gap, and no measurable "
    "span of events. Do not read the counts below as covering the whole window."
)

# Said whether or not any gap was recorded: a gap row can only appear here if the
# monitor was running and able to write it down. Time with no monitor running is now
# subtracted from the capture-session ledger instead, so this caveat names what is
# genuinely still invisible rather than over-claiming that every outage is missing.
UNRECORDED_GAP_CAVEAT = (
    "Coverage is measured from what the record contains. Stretches with no monitor "
    "running are subtracted when the capture-session ledger shows them, but an "
    "interruption inside a run that the device never got to write down cannot appear "
    "here, and neither can time before the first run or after the last. Treat these "
    "figures as an upper bound on how much was observed."
)

NO_RECORDED_GAPS_NOTE = "No monitoring gaps were recorded within this span."

ABSENCE_NOTE = (
    "Hours that were not monitored are not quiet hours: no event could be recorded then, "
    "so the absence of an event in those hours is not evidence that no sound occurred."
)

# --- Off air: the monitor was not running at all -----------------------------------
#
# A gap row is written by the *running* monitor when its audio source fails. The most
# ordinary outage of all leaves no gap row: the monitor was simply not running (stopped
# for the day, rebooted, crashed, power cut). The capture-session ledger records it
# anyway, as a hole between one session's end and the next one's start, so these periods
# are named and dated here rather than quietly counted as monitored time.

OFF_AIR_REASON = "monitor not running"

OFF_AIR_HEADING = "Time the monitor was not running"

OFF_AIR_NOTE = (
    "In these periods no monitor was running, so nothing could be measured. They are "
    "counted as not monitored, not as quiet. No monitoring gap is recorded for them: "
    "writing one down requires a running monitor, and there was none."
)

NO_OFF_AIR_NOTE = "The capture-session record shows a monitor running for the whole of this span."

OFF_AIR_UNKNOWN_NOTE = (
    "This record carries no capture sessions, so periods when no monitor was running "
    "cannot be identified from it and are not subtracted below. The coverage figure "
    "therefore assumes the device was listening whenever no gap was recorded, which is "
    "the most generous reading the record allows."
)


def _coverage_sentence(report: ViolationReport) -> str:
    """The one-line coverage claim, or the stated limit when it cannot be computed."""
    monitored, wall = report.monitored_hours, report.wall_clock_hours
    if monitored is None or wall is None:
        return COVERAGE_UNKNOWN_NOTE
    pct = (monitored / wall * 100.0) if wall else 0.0
    span = ""
    if report.span_start_iso and report.span_end_iso:
        span = f" The recorded span runs {report.span_start_iso} to {report.span_end_iso}."
    return (
        f"Over this reporting window the device monitored {monitored:.1f} of {wall:.1f} "
        f"wall-clock hours ({pct:.0f}%); the remaining {report.unmonitored_hours:.1f} "
        f"hours are shown as not monitored rather than quiet.{span}"
    )


def _off_air_sentence(report: ViolationReport) -> str:
    """What the record can say about time with no monitor running."""
    if report.off_air is None:
        return OFF_AIR_UNKNOWN_NOTE
    if not report.off_air:
        return NO_OFF_AIR_NOTE
    hours = report.off_air_hours or 0.0
    return f"No monitor was running for {hours:.1f} of these hours. {OFF_AIR_NOTE}"


def coverage_text_lines(report: ViolationReport) -> list[str]:
    """The coverage statement as plain-text lines, for the CSV comment preamble."""
    lines = [COVERAGE_HEADING, "", _coverage_sentence(report), "", ABSENCE_NOTE, ""]
    lines.append(UNRECORDED_GAP_CAVEAT)
    if report.gaps:
        lines += ["", "Recorded monitoring gaps (no data could be collected):"]
        lines += [
            f"  - {g.start_iso} to {g.end_iso} ({_fmt_seconds(g.seconds)}, {g.reason})"
            for g in report.gaps
        ]
    else:
        lines += ["", NO_RECORDED_GAPS_NOTE]
    lines += ["", OFF_AIR_HEADING, "", _off_air_sentence(report)]
    lines += [
        f"  - {g.start_iso} to {g.end_iso} ({_fmt_seconds(g.seconds)})"
        for g in report.off_air or []
    ]
    return lines


def _coverage_cell(hours: float | None) -> str:
    """An hours figure for the summary list, or an explicit not-determined marker."""
    return "not determined" if hours is None else f"{hours:.1f} h"


def coverage_html(report: ViolationReport) -> str:
    """The coverage block: a prominent banner plus the recorded-gap detail.

    Rendered unconditionally. When the figures exist it states them; when they do not it
    states that they could not be determined. There is no branch in which the document
    shows counts and says nothing about the time they were counted over.
    """
    known = report.monitored_hours is not None and report.wall_clock_hours is not None
    banner_class = "banner" if not known or report.unmonitored_hours else "banner banner-ok"
    banner = (
        f'<aside class="{banner_class}" role="note" aria-label="{COVERAGE_HEADING}">\n'
        f"<strong>{escape(COVERAGE_HEADING)}:</strong> {escape(_coverage_sentence(report))} "
        f"{escape(ABSENCE_NOTE)}\n"
        "</aside>"
    )
    if report.gaps:
        gap_rows = "".join(
            f'<tr><th scope="row">{escape(g.start_iso)}</th>'
            f"<td>{escape(g.end_iso)}</td>"
            f"<td>{_fmt_seconds(g.seconds)}</td>"
            f"<td>{escape(g.reason)}</td></tr>"
            for g in report.gaps
        )
        detail = (
            "<table><caption>Recorded monitoring gaps — no data could be collected in "
            'these periods</caption><thead><tr><th scope="col">Gap start</th>'
            '<th scope="col">Gap end</th><th scope="col">Length</th>'
            f'<th scope="col">Reason</th></tr></thead><tbody>{gap_rows}</tbody></table>'
        )
    else:
        detail = f"<p>{escape(NO_RECORDED_GAPS_NOTE)}</p>"
    return (
        f"{banner}\n"
        "<h3>Recorded monitoring gaps</h3>\n"
        f"{detail}\n"
        f'<div class="note"><p>{escape(UNRECORDED_GAP_CAVEAT)}</p></div>\n'
        f"{_off_air_html(report)}"
    )


def _off_air_html(report: ViolationReport) -> str:
    """The off-air block: when no monitor was running, or why that cannot be said.

    Rendered unconditionally alongside the gap ledger, and kept separate from it: a
    recorded gap and an unrun monitor are different facts, and "no monitoring gaps were
    recorded" sitting alone under a 20% coverage figure reads as "nothing was wrong".
    """
    if report.off_air:
        rows = "".join(
            f'<tr><th scope="row">{escape(g.start_iso)}</th>'
            f"<td>{escape(g.end_iso)}</td>"
            f"<td>{_fmt_seconds(g.seconds)}</td></tr>"
            for g in report.off_air
        )
        detail = (
            "<table><caption>Periods with no monitor running — nothing could be "
            'measured</caption><thead><tr><th scope="col">Off air from</th>'
            '<th scope="col">Off air until</th><th scope="col">Length</th>'
            f"</tr></thead><tbody>{rows}</tbody></table>"
        )
    else:
        detail = ""
    return (
        f"<h3>{escape(OFF_AIR_HEADING)}</h3>\n"
        f'<div class="note"><p>{escape(_off_air_sentence(report))}</p></div>\n'
        f"{detail}"
    )


def violations_to_csv(
    events: list[Event],
    path: str | Path,
    *,
    quiet_hours: QuietSchedule,
    tz: tzinfo = timezone.utc,
    tz_name: str = "UTC",
    offsets_db: Sequence[float] | None = None,
    basis: Sequence[str] | None = None,
    gaps: list[Gap] | None = None,
    sessions: Sequence[Session] | None = None,
) -> int:
    """Write every event with a within/outside-quiet-hours flag. Returns rows written.

    The export is honest by construction: it lists *all* events, not only the flagged
    ones, so a reader can see the full picture rather than a cherry-picked subset; each
    row records the calibration offset included in its levels (0.0 = raw dBFS) and a
    `monitored` column marking whether it fell in a period of confirmed coverage; and the
    "what this can and cannot prove" cover block (R1) plus the monitoring-coverage
    statement are written as a leading ``#`` comment preamble so both caveats travel with
    the file; data rows below it are unchanged.
    """
    report = compute_violations(
        events,
        quiet_hours=quiet_hours,
        tz=tz,
        tz_name=tz_name,
        offsets_db=offsets_db,
        basis=basis,
        gaps=gaps,
        sessions=sessions,
    )
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        for line in [*cover_text_lines(), "", *coverage_text_lines(report)]:
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
                    f"{r.calibration_offset_db:+.1f}",
                    r.calibration_basis,
                    _anatomy_cell(r.rise_time_s),
                    _anatomy_cell(r.loud6_s),
                    _anatomy_cell(r.longest_run_s),
                    "yes" if r.within_quiet_hours else "no",
                    f"{r.seconds_within_quiet_hours:.1f}",
                    report.window,
                    "yes" if r.monitored else "no",
                    r.coarse_tag or "",
                ]
            )
    return len(report.rows)


HONEST_SCOPE_NOTE = (
    "A row marked “within quiet hours” means only that this device measured a sound level "
    "above the detection threshold, starting during the quiet-hours window. It is not proof "
    "of the source of the sound or of who caused it. Event *counts* are attributed by their "
    "start time (a count cannot be fractional); the “seconds within quiet hours” column "
    "instead pro-rates each event's duration across the quiet-window boundary, so an event "
    "that begins before the window and ends inside it contributes only the seconds that "
    "actually fell in quiet hours."
)


def build_violation_report_html(
    report: ViolationReport,
    *,
    threshold_dbfs: float,
    min_duration_s: float,
    generated_at: str,
    calibrated: bool,
    multi_epoch: bool = False,
    back_applied_note: str | None = None,
    title: str = "Olive's Bark Logger — Quiet-Hours Report",
) -> str:
    """Render a standalone, accessible HTML quiet-hours violation report.

    Honest posture is mandatory and unconditional: the no-source and relative-dBFS
    limitations, the scope note, and the monitoring-coverage statement are always
    present, mirroring the main report. Coverage is printed in the Summary block above
    the counts, not buried in Limitations, because it is what makes the counts readable:
    "1 event in quiet hours" over 1.5 monitored hours is a different claim from the same
    count over 9.5.
    `calibrated` must reflect the calibration actually applied to the rows (the store's
    history, not a config field); `multi_epoch` discloses that more than one offset is
    in play across the window, in which case each row's own offset column governs.
    `back_applied_note` (from `report.render.back_applied_sentence`) discloses rows that
    predate the first calibration and carry its offset retroactively; it is rendered
    with the calibration statement whenever given, single- or multi-epoch alike.
    """
    if report.rows:
        body_rows = "".join(
            f'<tr><th scope="row">{escape(r.start_iso)}</th>'
            f"<td>{escape('yes' if r.within_quiet_hours else 'no')}</td>"
            f"<td>{escape('yes' if r.monitored else 'no')}</td>"
            f"<td>{_fmt_seconds(r.duration_s)}</td>"
            f"<td>{r.peak_dbfs:.1f}</td><td>{r.avg_dbfs:.1f}</td>"
            f"<td>{r.calibration_offset_db:+.1f}</td>"
            f"<td>{escape(r.calibration_basis)}</td>"
            f"<td>{_anatomy_cell(r.rise_time_s)}</td>"
            f"<td>{_anatomy_cell(r.loud6_s)}</td>"
            f"<td>{_anatomy_cell(r.longest_run_s)}</td>"
            f"<td>{escape(r.coarse_tag or '')}</td></tr>"
            for r in report.rows
        )
        table = (
            "<table><caption>Every logged event, flagged against the quiet-hours "
            "window. “Monitored” is no when the event overlaps a recorded monitoring "
            "gap, so a reading taken at the edge of an outage is marked as one."
            "</caption><thead><tr>"
            '<th scope="col">Start (local)</th>'
            '<th scope="col">Within quiet hours</th>'
            '<th scope="col">Monitored</th>'
            '<th scope="col">Duration</th>'
            '<th scope="col">Peak (dBFS)</th>'
            '<th scope="col">Avg (dBFS)</th>'
            '<th scope="col">Calibration offset (dB)</th>'
            '<th scope="col">Offset basis</th>'
            '<th scope="col">Rise (s)</th>'
            '<th scope="col">Loud +6 dB (s)</th>'
            '<th scope="col">Longest run (s)</th>'
            '<th scope="col">Coarse tag</th>'
            f"</tr></thead><tbody>{body_rows}</tbody></table>"
        )
    else:
        table = "<p>No events have been logged, so there is nothing to flag.</p>"

    if multi_epoch:
        calib_line = (
            "This window spans more than one calibration epoch: each event's level is "
            "adjusted by the calibration offset in force when it was measured (shown per "
            "row above, and per epoch in the main report). Calibrated readings "
            "approximate SPL but remain estimates; events measured under a zero offset "
            "remain relative dBFS."
        )
    else:
        calib_line = (
            "A calibration offset is applied, so levels approximate SPL but remain estimates."
            if calibrated
            else "No calibration offset is applied; levels are relative dBFS, not absolute SPL."
        )
    if back_applied_note:
        calib_line = f"{calib_line} Calibration postdates some readings: {back_applied_note}"

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
{coverage_html(report)}
<dl class="stats">
<dt>Monitored (wall-clock hours)</dt><dd>{_coverage_cell(report.monitored_hours)}</dd>
<dt>Reporting window (wall-clock hours)</dt><dd>{_coverage_cell(report.wall_clock_hours)}</dd>
<dt>Not monitored (wall-clock hours)</dt><dd>{_coverage_cell(report.unmonitored_hours)}</dd>
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
