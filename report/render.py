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

    from store import CalibrationEpoch, Session

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
:focus-visible { outline: 3px solid #3b6ea5; outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
@media print {
  body { color: #000; background: #fff; }
  .skip { display: none; }
  figure.chart, table { break-inside: avoid; page-break-inside: avoid; }
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
        "Each event's level is adjusted by the offset that was in force when it was "
        "measured, so recalibrating never rewrote earlier numbers. The offsets applied are:"
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
        calendar_section = (
            "\n<h2>Calendar heatmap</h2>\n"
            "<p>Each cell is the number of sound-level events that began in that hour, by "
            "day and hour of day. Darker cells saw more events; the count is printed in "
            "every non-empty cell and repeated in the data table below, so the pattern "
            "does not depend on color. These are event counts only — never audio.</p>\n"
            + heatmap(
                chart_id="calendar",
                title="Events by day and hour",
                day_labels=heat_days,
                grid=heat_grid,
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

<h2>{METHODOLOGY_HEADING}</h2>
<p>Each ~{config.frame_size / config.sample_rate * 1000:.0f} ms frame of audio is read
into memory, reduced to a single root-mean-square level in dBFS, and then discarded.
A noise event is recorded when the level stays at or above
<strong>{config.threshold_dbfs:.0f} dBFS</strong> for at least
<strong>{config.min_duration_s:.1f} s</strong>; brief dips shorter than the
<strong>{config.debounce_s:.1f} s</strong> debounce do not split one event into many.
For each event we store start time, duration, and peak and average level — six numbers,
no audio. {calib_line}</p>
{calib_epochs_section}
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

    # Which epochs actually cover the events in this window? Only those drive the choice
    # between the single-offset path and the multi-epoch disclosure.
    epochs_in_window = _epochs_covering(history, events)

    if len(epochs_in_window) > 1:
        adjusted = [_apply_offset(ev, _offset_at(history, ev.start)) for ev in events]
        summary = summarize(adjusted, quiet_hours=config.quiet_hours, tz=config.tzinfo())
        latest = epochs_in_window[-1]
        return build_report(
            summary,
            config=config,
            generated_at=generated_at,
            calibration_offset=latest.offset,
            calibration_note=latest.note or config.calibration_note,
            calibration_epochs=epochs_in_window,
            session=session,
        )

    # Single-offset path: the whole window is under one calibration (or none -> config).
    if epochs_in_window:
        epoch = epochs_in_window[0]
        offset, note = epoch.offset, epoch.note or config.calibration_note
    elif history:
        offset, note = history[-1].offset, history[-1].note or config.calibration_note
    else:
        offset, note = config.calibration_offset, config.calibration_note
    adjusted = [_apply_offset(ev, offset) for ev in events]
    summary = summarize(adjusted, quiet_hours=config.quiet_hours, tz=config.tzinfo())
    return build_report(
        summary,
        config=config,
        generated_at=generated_at,
        calibration_offset=offset,
        calibration_note=note,
        session=session,
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

    if args.csv is not None:
        from store import EventStore

        from report.export import events_to_csv

        with EventStore(db_path) as store:
            rows = events_to_csv(store.events(), args.csv, tz=config.tzinfo())
        print(f"Wrote {args.csv} ({rows} rows).")

    if args.violations_csv is not None or args.violations_html is not None:
        from store import EventStore

        from report.violations import (
            build_violation_report_html,
            compute_violations,
            violations_to_csv,
        )

        with EventStore(db_path) as store:
            events = store.events()
        if args.violations_csv is not None:
            rows = violations_to_csv(
                events,
                args.violations_csv,
                quiet_hours=config.quiet_hours,
                tz=config.tzinfo(),
                tz_name=config.tz,
            )
            print(f"Wrote {args.violations_csv} ({rows} rows).")
        if args.violations_html is not None:
            report = compute_violations(
                events, quiet_hours=config.quiet_hours, tz=config.tzinfo(), tz_name=config.tz
            )
            vhtml = build_violation_report_html(
                report,
                threshold_dbfs=config.threshold_dbfs,
                min_duration_s=config.min_duration_s,
                generated_at=generated_at,
                calibrated=config.calibration_offset != 0.0,
            )
            args.violations_html.write_text(vhtml, encoding="utf-8")
            print(f"Wrote {args.violations_html} ({len(vhtml)} bytes).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
