"""Assemble the HTML noise report: summary, charts, and an honest methodology section.

Determinism: build_report takes `generated_at` as a preformatted string and reads only
the summary + config, so the same event log always yields byte-identical HTML (see the
snapshot test). The methodology and limitations sections are not optional — they are
written here unconditionally, and a merge-blocking test asserts their presence.
"""

from __future__ import annotations

import argparse
import dataclasses
from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from monitor.config import Config
from monitor.detector import Event

from report.aggregate import Summary, summarize
from report.charts import bar_chart, heatmap

if TYPE_CHECKING:
    from datetime import tzinfo

    from store import CalibrationEpoch, Gap, Session

# Phrases the report-content gate checks for. Keeping them as constants makes the
# contract between the renderer and the test explicit.
METHODOLOGY_HEADING = "Methodology"
LIMITATIONS_HEADING = "Limitations"
RELATIVE_DBFS_NOTE = (
    "Levels are measured in dBFS, which is relative to digital full scale, not "
    "absolute sound pressure level (SPL) in dB. Without calibration against a "
    "reference meter, treat the numbers as relative, not absolute."
)
NO_SOURCE_NOTE = (
    "This tool measures sound levels only. It cannot prove what made a sound or "
    "where it came from; it does not record or identify any voice or source."
)

# R5 — reader-facing "why there is deliberately no audio" note. The rationale already
# lives in docs/audits/recording-law-notes.md; this surfaces it to the neighbor / PM /
# board who reads the report, so the absence of audio reads as a privacy choice, not as
# missing data. General information, not jurisdiction-specific legal advice.
NO_AUDIO_RATIONALE = (
    "This device measures sound levels only — it never records, stores, or transmits any "
    "audio. That is a deliberate privacy choice, not missing data: each level reading is "
    "computed in memory and immediately discarded, so no speech and nothing intelligible "
    "is ever kept. There is no recording of anyone in this home or next door that could be "
    "leaked, subpoenaed, or misused. Recording a household or a neighbor can also raise "
    "consent and eavesdropping concerns under some recording laws; measuring levels only "
    "sidesteps that by never capturing content. (General information, not legal advice — "
    "check the rules where you live.)"
)

# R1 — a single, reusable plain-language "What this can and cannot prove" cover block.
# It restates limitations that already hold elsewhere in the report; it adds prominence,
# never a new claim. The same block is prepended to the report and to every exported
# artifact (the violations HTML and CSV) so the caveat travels with the file.
COVER_CAN = (
    "When sound at this device crossed a set loudness threshold, and for how long, with "
    "timestamps — an honest, time-stamped record of the pattern.",
    "How that pattern lines up with a quiet-hours window you configure.",
)
COVER_CANNOT = (
    "What made a sound, or who caused it — no audio is recorded, so there is no source "
    "attribution.",
    "Absolute loudness in dB SPL or dB(A): uncalibrated readings are relative dBFS, not "
    "the units an ordinance, lease, or HOA rule is written in.",
    "That any law, lease, or rule was broken — only the relevant authority decides that, "
    "and being within quiet hours is not the same as a violation.",
    "Anything about a place this device was not in — readings are specific to this "
    "microphone in this spot, and change if it moves.",
)
COVER_PRIVACY = (
    "By design no audio is ever recorded, stored, or transmitted, so there is nothing to "
    "leak, subpoena, or misuse. This is general information, not legal advice; verify your "
    "local rule before relying on these numbers."
)


def cover_text_lines() -> list[str]:
    """The cover block as plain-text lines, for the comment preamble of CSV exports."""
    lines = ["What this can and cannot prove", "", "What it can show:"]
    lines += [f"  - {x}" for x in COVER_CAN]
    lines += ["", "What it cannot prove:"]
    lines += [f"  - {x}" for x in COVER_CANNOT]
    lines += ["", COVER_PRIVACY]
    return lines


def cover_html() -> str:
    """The R1 cover block as an accessible HTML <section>. Deterministic; no new claims."""
    can = "".join(f"<li>{escape(x)}</li>" for x in COVER_CAN)
    cannot = "".join(f"<li>{escape(x)}</li>" for x in COVER_CANNOT)
    return (
        '<section class="cover" aria-label="What this report can and cannot prove">\n'
        "<h2>What this can and cannot prove</h2>\n"
        "<p><strong>What it can show:</strong></p>\n"
        f"<ul>{can}</ul>\n"
        "<p><strong>What it cannot prove:</strong></p>\n"
        f"<ul>{cannot}</ul>\n"
        f'<p class="note">{escape(COVER_PRIVACY)}</p>\n'
        "</section>"
    )


_STYLE = """
:root { color-scheme: light dark; }
body { font: 16px/1.5 system-ui, sans-serif; margin: 0; color: #111; background: #fff; }
.skip { position: absolute; left: -999px; }
.skip:focus { left: 8px; top: 8px; position: fixed; background: #fff; padding: 8px; }
main { max-width: 60rem; margin: 0 auto; padding: 1.5rem; }
h1 { font-size: 1.6rem; } h2 { font-size: 1.25rem; margin-top: 2rem; }
dl.stats { display: grid; grid-template-columns: max-content 1fr; gap: .25rem 1rem; }
dl.stats dt { font-weight: 600; }
figure.chart { margin: 1rem 0; border: 1px solid #ccc; padding: 1rem; }
figure.chart figcaption { font-weight: 600; margin-bottom: .5rem; }
table { border-collapse: collapse; margin-top: .75rem; width: 100%; }
caption { text-align: left; font-style: italic; margin-bottom: .25rem; }
th, td { border: 1px solid #bbb; padding: .25rem .5rem; text-align: left; }
.note { background: #f3f3f3; border-left: 4px solid #3b6ea5; padding: .75rem 1rem; }
section.cover { border: 1px solid #bbb; padding: .5rem 1.25rem 1rem; margin: 1rem 0; background: #fafafa; }
section.cover ul { margin: .25rem 0; }
.banner { padding: .75rem 1rem; margin: 1rem 0; border: 2px solid #b35900; background: #fff4e5; }
.banner.banner-ok { border-color: #2f6f3e; background: #eef7ef; }
:focus-visible { outline: 3px solid #3b6ea5; outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
@media print {
  body { color: #000; background: #fff; }
  .skip { display: none; }
  .banner { border: 2px solid #000; }
  section.cover, figure.chart, table { break-inside: avoid; page-break-inside: avoid; }
  main { max-width: none; }
}
""".strip()


def _fmt_seconds(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f} s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f} min"
    return f"{minutes / 60:.1f} h"


def _conditions_html(session: Session | None) -> str:
    """Measurement-conditions paragraph from the latest capture session (lineage)."""
    if session is None:
        return (
            "<p>Measurement conditions for this report were not recorded "
            "(events predate session tracking).</p>"
        )
    mic = f", microphone {escape(session.mic_model)}" if session.mic_model else ""
    placement = f" Placement: {escape(session.placement_note)}." if session.placement_note else ""
    total = session.frames_seen + session.frames_dropped
    coverage = (
        f" Frame coverage in the most recent session was "
        f"<strong>{session.frame_coverage:.1%}</strong> "
        f"({session.frames_seen:,} of {total:,} frames processed)."
        if total
        else ""
    )
    return (
        f"<p>Captured by device <strong>{escape(session.device_label)}</strong>{mic}."
        f"{placement}{coverage}</p>"
    )


PARAM_CHANGE_NOTE = (
    "Detection settings changed during this record; each event is described under the "
    "parameters in force when it was logged."
)


def _param_key(session: Session) -> tuple[object, ...]:
    """The detection-parameter tuple that defines a parameter epoch for a session."""
    return (
        session.threshold_dbfs,
        session.min_duration_s,
        session.debounce_s,
        session.sample_rate,
        session.frame_size,
    )


def _param_epochs(sessions: list[Session]) -> list[Session]:
    """Distinct detection-parameter sets in chronological order, each represented by the
    earliest session that used it. `sessions` is expected oldest-first."""
    epochs: dict[tuple[object, ...], Session] = {}
    for s in sessions:
        epochs.setdefault(_param_key(s), s)
    return list(epochs.values())


def _methodology_html(config: Config, calib_line: str, sessions: list[Session] | None) -> str:
    """The Methodology block. With one detection-parameter set (or none recorded) this is
    the single honest paragraph, sourcing values from the session when available and
    otherwise from config. When the parameters changed across sessions, it becomes a small
    table of parameter epochs plus a disclosure that events are described under the
    settings in force when they were logged."""
    epochs = _param_epochs(sessions) if sessions else []

    if len(epochs) > 1:
        rows = "".join(
            "<tr>"
            f'<th scope="row">{escape(_epoch_since(s, config))}</th>'
            f"<td>{_fmt_threshold(s.threshold_dbfs)}</td>"
            f"<td>{_fmt_secs_param(s.min_duration_s)}</td>"
            f"<td>{_fmt_secs_param(s.debounce_s)}</td>"
            f"<td>{escape(_fmt_sampling(s.sample_rate, s.frame_size))}</td>"
            "</tr>"
            for s in epochs
        )
        return (
            "<p>Each frame of audio is read into memory, reduced to a single "
            "root-mean-square level in dBFS, and then discarded. A noise event is recorded "
            "when the level stays at or above the threshold for at least the minimum "
            "duration; brief dips shorter than the debounce do not split one event into "
            "many. For each event we store start time, duration, and peak and average "
            f"level — six numbers, no audio. {calib_line}</p>\n"
            "<table><caption>Detection-parameter epochs</caption>"
            '<thead><tr><th scope="col">Since</th><th scope="col">Threshold</th>'
            '<th scope="col">Min duration</th><th scope="col">Debounce</th>'
            '<th scope="col">Sampling</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>\n"
            f"<p>{escape(PARAM_CHANGE_NOTE)}</p>"
        )

    # Single parameter set (or none recorded): source from the one epoch when present,
    # falling back to config so pre-provenance records still render truthfully.
    epoch = epochs[0] if epochs else None
    threshold = _param_or(epoch, "threshold_dbfs", config.threshold_dbfs)
    min_duration = _param_or(epoch, "min_duration_s", config.min_duration_s)
    debounce = _param_or(epoch, "debounce_s", config.debounce_s)
    sample_rate = _param_or(epoch, "sample_rate", config.sample_rate)
    frame_size = _param_or(epoch, "frame_size", config.frame_size)
    return (
        f"<p>Each ~{frame_size / sample_rate * 1000:.0f} ms frame of audio is read\n"
        "into memory, reduced to a single root-mean-square level in dBFS, and then "
        "discarded.\n"
        "A noise event is recorded when the level stays at or above\n"
        f"<strong>{threshold:.0f} dBFS</strong> for at least\n"
        f"<strong>{min_duration:.1f} s</strong>; brief dips shorter than the\n"
        f"<strong>{debounce:.1f} s</strong> debounce do not split one event into many.\n"
        "For each event we store start time, duration, and peak and average level — six "
        "numbers,\n"
        f"no audio. {calib_line}</p>"
    )


def _param_or(session: Session | None, attr: str, fallback: float | int) -> float | int:
    if session is None:
        return fallback
    value = getattr(session, attr)
    return fallback if value is None else value


def _epoch_since(session: Session, config: Config) -> str:
    return datetime.fromtimestamp(session.started_at, tz=config.tzinfo()).date().isoformat()


def _fmt_threshold(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f} dBFS"


def _fmt_secs_param(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} s"


def _fmt_sampling(sample_rate: int | None, frame_size: int | None) -> str:
    if sample_rate is None or frame_size is None:
        return "—"
    return f"{sample_rate} Hz / {frame_size}-sample frames"


def _epoch_index_at(history: list[CalibrationEpoch], ts: float) -> int | None:
    """Index into `history` (ascending by effective_from) of the epoch in force at `ts`.

    A timestamp before the first epoch resolves to that first epoch (epoch 0 covers all
    historical rows); None only when the history is empty.
    """
    if not history:
        return None
    chosen = 0
    for i, epoch in enumerate(history):
        if epoch.effective_from <= ts:
            chosen = i
        else:
            break
    return chosen


def _offset_at(history: list[CalibrationEpoch], ts: float) -> float:
    """The calibration offset in force at `ts`, or 0.0 when no calibration exists."""
    idx = _epoch_index_at(history, ts)
    return 0.0 if idx is None else history[idx].offset


def _epochs_covering(
    history: list[CalibrationEpoch], events: list[Event]
) -> list[CalibrationEpoch]:
    """The subset of epochs that are in force for at least one of `events`, in order."""
    if not history or not events:
        return []
    used = {idx for ev in events if (idx := _epoch_index_at(history, ev.start)) is not None}
    return [history[i] for i in sorted(used)]


def _apply_offset(event: Event, offset: float) -> Event:
    """Return the event with its stored raw levels shifted by a calibration offset."""
    if offset == 0.0:
        return event
    return dataclasses.replace(
        event, peak_level=event.peak_level + offset, avg_level=event.avg_level + offset
    )


def _per_event_offsets(
    events: list[Event], history: list[CalibrationEpoch], config: Config
) -> list[float]:
    """The calibration offset applied to each event at render time (parallel list).

    This is the single resolver every rendered artifact must go through — the HTML
    report and the CSV/violations exports all adjust levels with exactly these values,
    so no two artifacts generated from the same log can disagree numerically.
    Attribution is by event *start*: an event that straddles a recalibration uses the
    epoch in force when it began. With no calibration history at all, the config's
    bootstrap offset applies uniformly (the deprecated-but-supported fallback).
    """
    if history:
        return [_offset_at(history, ev.start) for ev in events]
    return [config.calibration_offset] * len(events)


def _fmt_effective_from(effective_from: float, tz: tzinfo) -> str:
    """Human label for an epoch boundary; epoch 0 is the start of the record."""
    if effective_from <= 0.0:
        return "start of record"
    return datetime.fromtimestamp(effective_from, tz=tz).strftime("%Y-%m-%d %H:%M %Z")


def _calibration_epochs_html(epochs: list[CalibrationEpoch], *, tz: tzinfo) -> str:
    """A per-epoch offsets table plus a disclosure line, for a multi-epoch window."""
    rows = "".join(
        f'<tr><th scope="row">{escape(_fmt_effective_from(e.effective_from, tz))}</th>'
        f"<td>{e.offset:+.1f} dB</td>"
        f"<td>{escape(e.reference_instrument) if e.reference_instrument else '—'}</td>"
        f"<td>{escape(e.note) if e.note else '—'}</td></tr>"
        for e in epochs
    )
    return (
        "\n<p>This reporting window spans <strong>more than one calibration epoch</strong>. "
        "Each event's level is adjusted by the offset that was in force when it began, "
        "so recalibrating does not rewrite stored numbers. One caveat: events stored by "
        "versions of this tool from before the calibration history existed had any "
        "then-configured offset already included in their stored levels; if that offset "
        "was nonzero, those older rows render over-adjusted here. The database records "
        "when that upgrade happened, so affected rows are identifiable. "
        "The offsets applied are:"
        "</p>\n"
        "<table><caption>Calibration offsets by epoch</caption>"
        '<thead><tr><th scope="col">Effective from</th><th scope="col">Offset</th>'
        '<th scope="col">Reference instrument</th><th scope="col">Note</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def build_report(
    summary: Summary,
    *,
    config: Config,
    generated_at: str,
    calibration_offset: float | None = None,
    calibration_note: str | None = None,
    calibration_epochs: list[CalibrationEpoch] | None = None,
    session: Session | None = None,
    sessions: list[Session] | None = None,
    unmonitored: set[tuple[str, int]] | None = None,
    monitored_hours: float | None = None,
    wall_clock_hours: float | None = None,
    title: str = "Olive's Bark Logger — Noise Report",
) -> str:
    """Render the full report as a single self-contained HTML string.

    When `calibration_epochs` holds more than one epoch, a per-epoch offsets table and a
    recalibration disclosure are rendered; otherwise the single-offset path is used and
    `calibration_offset`/`calibration_note` describe the one offset in force.
    """
    offset = config.calibration_offset if calibration_offset is None else calibration_offset
    note = config.calibration_note if calibration_note is None else calibration_note
    epochs = calibration_epochs or []
    multi_epoch = len(epochs) > 1
    calibrated = offset != 0.0
    conditions_html = _conditions_html(session)

    hour_chart = bar_chart(
        chart_id="by-hour",
        title="Events by hour of day",
        labels=[f"{h:02d}" for h in range(24)],
        values=[float(summary.by_hour.get(h, 0)) for h in range(24)],
        value_caption="events",
    )
    day_labels = list(summary.by_day.keys())
    day_chart = bar_chart(
        chart_id="by-day",
        title="Events by day",
        labels=day_labels if day_labels else ["(no data)"],
        values=[float(v) for v in summary.by_day.values()] if day_labels else [0.0],
        value_caption="events",
    )

    if summary.by_day_hour:
        heat_days = list(summary.by_day_hour.keys())
        heat_grid = [[summary.by_day_hour[d][h] for h in range(24)] for d in heat_days]
        unmon_note = (
            " Hours the device was not listening are hatched and labeled "
            '"not monitored" in the table, so absence of data is never read as quiet.'
            if unmonitored
            else ""
        )
        calendar_section = (
            "\n<h2>Calendar heatmap</h2>\n"
            "<p>Each cell is the number of sound-level events that began in that hour, by "
            "day and hour of day. Darker cells saw more events; the count is printed in "
            "every non-empty cell and repeated in the data table below, so the pattern "
            "does not depend on color. These are event counts only — never audio."
            f"{unmon_note}</p>\n"
            + heatmap(
                chart_id="calendar",
                title="Events by day and hour",
                day_labels=heat_days,
                grid=heat_grid,
                unmonitored=unmonitored,
            )
        )
    else:
        calendar_section = (
            "\n<h2>Calendar heatmap</h2>\n<p>No events have been logged yet, so there is "
            "no calendar to show.</p>"
        )

    qh = config.quiet_hours
    quiet_window = f"{qh.start_hour:02d}:00–{qh.end_hour:02d}:00"  # noqa: RUF001 - intentional en dash

    stats = {
        "Total events": str(summary.event_count),
        "Total loud time": _fmt_seconds(summary.total_loud_seconds),
        "Longest event": _fmt_seconds(summary.longest_event_seconds),
        "Loudest peak": f"{summary.loudest_peak_dbfs:.1f} dBFS",
        "Mean peak": f"{summary.mean_peak_dbfs:.1f} dBFS",
        f"Events during quiet hours ({quiet_window})": str(summary.quiet_hours_event_count),
        "Loud time during quiet hours": _fmt_seconds(summary.quiet_hours_loud_seconds),
    }
    stats_html = "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in stats.items())

    if multi_epoch:
        calib_line = (
            "Levels are adjusted for calibration at render time from an append-only "
            "history; because this window spans more than one calibration epoch, each "
            "event uses the offset in force when it was measured (see the table below)."
        )
        calib_epochs_section = _calibration_epochs_html(epochs, tz=config.tzinfo())
    else:
        calib_line = (
            f"A calibration offset of {offset:+.1f} dB is applied "
            f"({escape(note)}). Readings approximate SPL but remain estimates."
            if calibrated
            else f"No calibration offset is applied ({escape(note)})."
        )
        calib_epochs_section = ""

    # R2 — unmissable calibration-honesty banner. Uncalibrated readings must never get to
    # look like dB(A)/SPL; when calibrated, the reference-instrument provenance (carried in
    # the calibration note) is surfaced prominently rather than buried in methodology.
    if calibrated:
        banner_html = (
            '<aside class="banner banner-ok" role="note" aria-label="Calibration status">\n'
            f"<strong>Calibrated.</strong> An offset of {offset:+.1f} dB is applied "
            f"({escape(note)}). Readings approximate sound level (SPL) but remain estimates "
            "affected by microphone, placement, and room acoustics.\n"
            "</aside>"
        )
    else:
        banner_html = (
            '<aside class="banner" role="note" aria-label="Calibration status">\n'
            "<strong>Uncalibrated — these readings are relative, not dB(A).</strong> "
            "Levels are relative dBFS, not absolute sound level in dB(A) or dB SPL. Do not "
            "read them as the decibel numbers an ordinance or lease specifies; only their "
            "pattern relative to each other on this device is meaningful. Run "
            "<code>olive-calibrate</code> against a reference meter to estimate SPL (still "
            "an estimate, not a Class 1/2 sound-level-meter reading).\n"
            "</aside>"
        )

    # R3 — quiet-hours duration rollup. Ordinances/CC&Rs commonly key on accumulated
    # duration in a day; this totals detected loud time within the configured window, per
    # day, WITHOUT rendering a verdict. The no-verdict framing is mandatory.
    if summary.quiet_hours_loud_seconds_by_day:
        rollup_rows = "".join(
            f'<tr><th scope="row">{escape(day)}</th><td>{_fmt_seconds(secs)}</td></tr>'
            for day, secs in summary.quiet_hours_loud_seconds_by_day.items()
        )
        rollup_section = (
            "\n<h2>Quiet-hours duration rollup</h2>\n"
            "<p>Detected loud time within the quiet-hours window, totaled per day and "
            "attributed by each event's start time. Some ordinances and CC&amp;Rs key on "
            "accumulated duration in a day — figures of around <strong>30 minutes "
            "continuous</strong> or <strong>60 minutes intermittent</strong> are sometimes "
            "cited — but the threshold, the unit, and the definition vary by jurisdiction.</p>\n"
            '<div class="note"><p>This is a measurement, not a determination. Being within '
            "quiet hours is not the same as a violation, and only the relevant authority can "
            "decide whether a rule was broken. Compare these durations against your own local "
            "ordinance, lease, or HOA rule.</p></div>\n"
            "<table><caption>Loud time within quiet hours, per day</caption>"
            '<thead><tr><th scope="col">Day</th>'
            '<th scope="col">Loud time within quiet hours</th></tr></thead>'
            f"<tbody>{rollup_rows}</tbody></table>"
        )
    else:
        rollup_section = (
            "\n<h2>Quiet-hours duration rollup</h2>\n"
            "<p>No events fell within the quiet-hours window, so there is nothing to roll "
            "up. Being within quiet hours is not the same as a violation in any case.</p>"
        )

    methodology_html = _methodology_html(config, calib_line, sessions)

    coverage_html = ""
    if monitored_hours is not None and wall_clock_hours is not None:
        coverage_html = (
            f"<p>Over this reporting window the device monitored "
            f"{monitored_hours:.1f} of {wall_clock_hours:.1f} wall-clock hours; the "
            "remainder is shown as not monitored rather than quiet.</p>\n"
        )

    tags_section = ""
    if summary.by_tag:
        rows = "".join(
            f'<tr><th scope="row">{escape(tag)}</th><td>{count}</td></tr>'
            for tag, count in summary.by_tag.items()
        )
        tags_section = (
            "\n<h2>Event types (coarse hint)</h2>\n"
            "<p>A crude, on-device classification of each event as bark-like or ambient, "
            "from sound shape only. It is a hint, not a fact, and it cannot identify a "
            "source.</p>\n"
            "<table><caption>Events by coarse type</caption>"
            '<thead><tr><th scope="col">Type</th><th scope="col">Events</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
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
<p>Generated {escape(generated_at)}. This report summarizes sound-level <em>events</em> —
when sound crossed a threshold and for how long. No audio was recorded, stored, or
transmitted to produce it.</p>

{cover_html()}

{banner_html}

<h2>Summary</h2>
<dl class="stats">{stats_html}</dl>

<h2>Measurement conditions</h2>
{conditions_html}

<h2>Distributions</h2>
{hour_chart}
{day_chart}
{calendar_section}

{tags_section}
<h2>Quiet hours</h2>
<p>Quiet-hours window: <strong>{quiet_window}</strong> in time zone
<strong>{escape(config.tz)}</strong> (daylight-saving aware). Of {summary.event_count}
total events, <strong>{summary.quiet_hours_event_count}</strong> fell within quiet hours,
totaling {_fmt_seconds(summary.quiet_hours_loud_seconds)} of loud time.</p>
{rollup_section}

<h2>Why there is deliberately no audio</h2>
<div class="note"><p>{escape(NO_AUDIO_RATIONALE)}</p></div>

<h2>{METHODOLOGY_HEADING}</h2>
{methodology_html}
{coverage_html}{calib_epochs_section}
<h2>{LIMITATIONS_HEADING}</h2>
<div class="note">
<p>{escape(RELATIVE_DBFS_NOTE)}</p>
<p>{escape(NO_SOURCE_NOTE)}</p>
<p>Microphone placement and room acoustics affect every reading; an event count
reflects this device in this spot, not an absolute fact about the building. These
numbers are offered to inform, not to manufacture a case.</p>
</div>
</main>
</body>
</html>
"""


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """Length of the overlap between intervals [a_start, a_end) and [b_start, b_end)."""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _unmonitored_buckets(
    gaps: list[Gap], day_hour: dict[str, dict[int, int]], tz: tzinfo
) -> set[tuple[str, int]]:
    """Which (day_label, hour) heatmap cells a gap covers.

    Only cells that appear in the heatmap (days that had events) and that hold zero
    events are marked, so a partly-monitored hour with a real event still shows its count.
    A gap is expanded hour by hour; each touched hour whose cell is empty becomes
    'not monitored'.
    """
    buckets: set[tuple[str, int]] = set()
    for gap in gaps:
        # Walk each clock hour the gap touches. Step by 3600 s from the gap start.
        t = gap.start
        while t < gap.end:
            dt = datetime.fromtimestamp(t, tz=tz)
            day = dt.date().isoformat()
            hour = dt.hour
            if day in day_hour and day_hour[day].get(hour, 0) == 0:
                buckets.add((day, hour))
            t += 3600.0
    return buckets


def _coverage_hours(
    events: list[Event], gaps: list[Gap], session: Session | None
) -> tuple[float, float] | None:
    """Monitored vs wall-clock hours over the reporting window, or None if undeterminable.

    The window spans the earliest observed moment to the latest across events, gaps, and
    the latest session. Time inside a recorded gap (including any stretch outside a
    session) is unmonitored; everything else is treated as monitored.
    """
    starts: list[float] = [e.start for e in events]
    ends: list[float] = [e.end for e in events]
    for g in gaps:
        starts.append(g.start)
        ends.append(g.end)
    if session is not None:
        starts.append(session.started_at)
        if session.ended_at is not None:
            ends.append(session.ended_at)
    if not starts or not ends:
        return None
    win_start, win_end = min(starts), max(ends)
    span = win_end - win_start
    if span <= 0:
        return None
    gap_seconds = sum(_overlap(g.start, g.end, win_start, win_end) for g in gaps)
    monitored = max(0.0, span - gap_seconds)
    return monitored / 3600.0, span / 3600.0


def generate_report_from_db(
    db_path: str,
    config: Config,
    *,
    generated_at: str,
) -> str:
    """Read events from the store and render the report. Deterministic given inputs."""
    from store import EventStore

    with EventStore(db_path) as store:
        events = store.events()  # raw dBFS levels; calibration is applied here, at render
        history = store.calibration_history()
        session = store.latest_session()
        gaps = store.gaps()
        sessions = store.sessions()

    # Which epochs actually cover the events in this window? Only those drive the choice
    # between the single-offset path and the multi-epoch disclosure. Levels are always
    # adjusted through the shared per-event resolver, the same one the exports use.
    tz = config.tzinfo()
    epochs_in_window = _epochs_covering(history, events)
    offsets = _per_event_offsets(events, history, config)
    adjusted = [_apply_offset(ev, off) for ev, off in zip(events, offsets)]
    summary = summarize(adjusted, quiet_hours=config.quiet_hours, tz=tz)

    # Monitoring-gap honesty: unmonitored heatmap buckets plus monitored-vs-wall-clock
    # coverage, rendered on both the single-offset and multi-epoch paths.
    unmonitored = _unmonitored_buckets(gaps, summary.by_day_hour, tz) if gaps else None
    coverage = _coverage_hours(events, gaps, session)
    monitored_hours, wall_clock_hours = coverage if coverage else (None, None)

    if len(epochs_in_window) > 1:
        latest = epochs_in_window[-1]
        return build_report(
            summary,
            config=config,
            generated_at=generated_at,
            calibration_offset=latest.offset,
            calibration_note=latest.note or config.calibration_note,
            calibration_epochs=epochs_in_window,
            session=session,
            sessions=sessions,
            unmonitored=unmonitored,
            monitored_hours=monitored_hours,
            wall_clock_hours=wall_clock_hours,
        )

    # Single-offset path: the whole window is under one calibration (or none -> config).
    if epochs_in_window:
        epoch = epochs_in_window[0]
        offset, note = epoch.offset, epoch.note or config.calibration_note
    elif history:
        offset, note = history[-1].offset, history[-1].note or config.calibration_note
    else:
        offset, note = config.calibration_offset, config.calibration_note
    return build_report(
        summary,
        config=config,
        generated_at=generated_at,
        calibration_offset=offset,
        calibration_note=note,
        session=session,
        sessions=sessions,
        unmonitored=unmonitored,
        monitored_hours=monitored_hours,
        wall_clock_hours=wall_clock_hours,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="olive-report",
        description="Generate an accessible HTML noise report from the event log.",
    )
    parser.add_argument("--config", type=Path, default=None, help="path to JSON config")
    parser.add_argument("--db", type=str, default=None, help="path to SQLite event log")
    parser.add_argument("--out", type=Path, default=Path("report.html"), help="output HTML path")
    parser.add_argument(
        "--generated-at",
        type=str,
        default=None,
        help="timestamp string for the report header (default: now, UTC)",
    )
    parser.add_argument(
        "--csv", type=Path, default=None, help="also export the event log to this CSV path"
    )
    parser.add_argument(
        "--violations-csv",
        type=Path,
        default=None,
        help="export every event flagged within/outside quiet hours to this CSV path",
    )
    parser.add_argument(
        "--violations-html",
        type=Path,
        default=None,
        help="render a standalone honest quiet-hours violation report to this HTML path",
    )
    args = parser.parse_args(argv)

    config = Config.load(args.config)
    db_path = args.db or config.db_path
    generated_at = args.generated_at or datetime.now(config.tzinfo()).strftime("%Y-%m-%d %H:%M %Z")

    html = generate_report_from_db(db_path, config, generated_at=generated_at)
    args.out.write_text(html, encoding="utf-8")
    print(f"Wrote {args.out} ({len(html)} bytes).")

    if args.csv is not None or args.violations_csv is not None or args.violations_html is not None:
        from store import EventStore

        with EventStore(db_path) as store:
            raw_events = store.events()  # raw dBFS; calibration is applied below, at render
            history = store.calibration_history()
            gaps = store.gaps()
        # Exports must agree numerically with the main report: the same render-time,
        # per-epoch calibration is applied to every exported artifact, and each CSV row
        # records the offset it received (raw = value - offset). The calibrated flag is
        # derived from the store's history, never from the deprecated config field.
        offsets = _per_event_offsets(raw_events, history, config)
        events = [_apply_offset(ev, off) for ev, off in zip(raw_events, offsets)]
        multi_epoch = len(set(offsets)) > 1
        if events:
            calibrated = all(off != 0.0 for off in offsets)
        else:  # nothing to adjust; disclose the calibration in force (store, then config)
            calibrated = (history[-1].offset if history else config.calibration_offset) != 0.0

        if args.csv is not None:
            from report.export import events_to_csv

            rows = events_to_csv(
                events, args.csv, tz=config.tzinfo(), offsets_db=offsets, gaps=gaps
            )
            print(f"Wrote {args.csv} ({rows} rows).")

        if args.violations_csv is not None or args.violations_html is not None:
            from report.violations import (
                build_violation_report_html,
                compute_violations,
                violations_to_csv,
            )

            if args.violations_csv is not None:
                rows = violations_to_csv(
                    events,
                    args.violations_csv,
                    quiet_hours=config.quiet_hours,
                    tz=config.tzinfo(),
                    tz_name=config.tz,
                    offsets_db=offsets,
                    gaps=gaps,
                )
                print(f"Wrote {args.violations_csv} ({rows} rows).")
            if args.violations_html is not None:
                report = compute_violations(
                    events,
                    quiet_hours=config.quiet_hours,
                    tz=config.tzinfo(),
                    tz_name=config.tz,
                    offsets_db=offsets,
                    gaps=gaps,
                )
                vhtml = build_violation_report_html(
                    report,
                    threshold_dbfs=config.threshold_dbfs,
                    min_duration_s=config.min_duration_s,
                    generated_at=generated_at,
                    calibrated=calibrated,
                    multi_epoch=multi_epoch,
                )
                args.violations_html.write_text(vhtml, encoding="utf-8")
                print(f"Wrote {args.violations_html} ({len(vhtml)} bytes).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
