"""Assemble the HTML noise report: summary, charts, and an honest methodology section.

Determinism: build_report takes `generated_at` as a preformatted string and reads only
the summary + config, so the same event log always yields byte-identical HTML (see the
snapshot test). The methodology and limitations sections are not optional — they are
written here unconditionally, and a merge-blocking test asserts their presence.
"""

from __future__ import annotations

import argparse
from datetime import datetime, tzinfo
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from monitor.config import Config

from report.aggregate import Summary, summarize
from report.charts import bar_chart, heatmap

if TYPE_CHECKING:
    from monitor.detector import Event
    from store import Gap, Session

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


def build_report(
    summary: Summary,
    *,
    config: Config,
    generated_at: str,
    calibration_offset: float | None = None,
    calibration_note: str | None = None,
    session: Session | None = None,
    unmonitored: set[tuple[str, int]] | None = None,
    monitored_hours: float | None = None,
    wall_clock_hours: float | None = None,
    title: str = "Olive's Bark Logger — Noise Report",
) -> str:
    """Render the full report as a single self-contained HTML string."""
    offset = config.calibration_offset if calibration_offset is None else calibration_offset
    note = config.calibration_note if calibration_note is None else calibration_note
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

    calib_line = (
        f"A calibration offset of {offset:+.1f} dB is applied "
        f"({escape(note)}). Readings approximate SPL but remain estimates."
        if calibrated
        else f"No calibration offset is applied ({escape(note)})."
    )

    coverage_line = ""
    if monitored_hours is not None and wall_clock_hours is not None:
        coverage_line = (
            f" Over this reporting window the device monitored "
            f"{monitored_hours:.1f} of {wall_clock_hours:.1f} wall-clock hours; the "
            "remainder is shown as not monitored rather than quiet."
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
no audio. {calib_line}{coverage_line}</p>

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
        events = store.events()
        calib = store.get_calibration()
        session = store.latest_session()
        gaps = store.gaps()
    tz = config.tzinfo()
    summary = summarize(
        events,
        quiet_hours=config.quiet_hours,
        tz=tz,
    )
    offset, note = calib if calib else (config.calibration_offset, config.calibration_note)
    unmonitored = _unmonitored_buckets(gaps, summary.by_day_hour, tz) if gaps else None
    coverage = _coverage_hours(events, gaps, session)
    monitored_hours, wall_clock_hours = coverage if coverage else (None, None)
    return build_report(
        summary,
        config=config,
        generated_at=generated_at,
        calibration_offset=offset,
        calibration_note=note,
        session=session,
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

    if args.csv is not None:
        from store import EventStore

        from report.export import events_to_csv

        with EventStore(db_path) as store:
            rows = events_to_csv(store.events(), args.csv, tz=config.tzinfo(), gaps=store.gaps())
        print(f"Wrote {args.csv} ({rows} rows).")  # noqa: T201

    if args.violations_csv is not None or args.violations_html is not None:
        from store import EventStore

        from report.violations import (
            build_violation_report_html,
            compute_violations,
            violations_to_csv,
        )

        with EventStore(db_path) as store:
            events = store.events()
            gaps = store.gaps()
        if args.violations_csv is not None:
            rows = violations_to_csv(
                events,
                args.violations_csv,
                quiet_hours=config.quiet_hours,
                tz=config.tzinfo(),
                tz_name=config.tz,
                gaps=gaps,
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
