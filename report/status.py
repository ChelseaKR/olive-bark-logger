"""Render a static, serverless status snapshot (``status.html``) for local ops.

The monitor runs headless; the deliverable is the report. But while it is running you
sometimes just want to glance at "is it alive, is it keeping up, was last night loud?"
without standing up a server or shipping a byte off the box. This module renders that
glance as a single self-contained HTML file the monitor rewrites next to its heartbeat,
so the operator can double-click it open at any time.

Same guarantees as the rest of the tool: pure standard library, no network, no audio —
only the derived level/coverage metadata already in the heartbeat and the event store.
The page reuses the report's stylesheet and structural-a11y conventions (lang, landmarks,
headings, scoped table headers) so the same accessibility floor applies here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from report.aggregate import Summary, summarize

# Reuse the report's stylesheet verbatim so the status page inherits the same
# reduced-motion, focus-visible, print and color-scheme handling (and stays a single
# source of truth for the look).
from report.render import _STYLE

if TYPE_CHECKING:
    from monitor.config import Config
    from store import EventStore

# How long we default to summarizing for the "last night" panel. A single window that
# comfortably covers the previous night regardless of when the operator looks.
DEFAULT_WINDOW_HOURS = 24
# Heartbeat freshness defaults to the original one-minute assumption for standalone
# callers. The monitor passes its configured checkpoint interval when rendering.
DEFAULT_HEARTBEAT_INTERVAL_S = 60.0

GAP_UNAVAILABLE_NOTE = (
    "Gap data unavailable for this status source. Frame coverage below still shows "
    "whether captured frames were dropped while the monitor was running."
)


@dataclass(frozen=True)
class StatusAggregates:
    """Everything the status page needs from the store, precomputed by the caller.

    Keeping this a plain value object (no store handle) makes ``render_status`` a pure
    function of its inputs, so it is trivial to unit-test with a synthetic summary.
    """

    summary: Summary
    quiet_window: str
    tz_name: str
    tz: tzinfo = timezone.utc
    window_hours: int = DEFAULT_WINDOW_HOURS
    busiest_hour: int | None = None
    # None means the caller could not supply gap data. An empty list means the ledger
    # was queried and no gaps overlapped the status window.
    gaps: list[str] | None = None


def collect_status_aggregates(
    store: EventStore,
    config: Config,
    *,
    now: float,
    window_hours: int = DEFAULT_WINDOW_HOURS,
) -> StatusAggregates:
    """Summarize the most recent ``window_hours`` of events from an open store."""
    tz = config.tzinfo()
    since = now - window_hours * 3600
    events = store.events(since=since)
    summary = summarize(events, quiet_hours=config.quiet_hours, tz=tz)
    busiest_hour: int | None = None
    if any(summary.by_hour.values()):
        busiest_hour = max(summary.by_hour, key=lambda h: summary.by_hour[h])
    gaps = [
        f"{_fmt_ts(gap.start, tz)}–{_fmt_ts(gap.end, tz)} "  # noqa: RUF001 - range dash
        f"({_fmt_duration(gap.duration)}, {gap.reason.replace('-', ' ')})"
        for gap in store.gaps(since=since, until=now)
    ]
    return StatusAggregates(
        summary=summary,
        quiet_window=config.quiet_hours.label(),
        tz_name=config.tz,
        tz=tz,
        window_hours=window_hours,
        busiest_hour=busiest_hour,
        gaps=gaps,
    )


def _fmt_age(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"{seconds:.0f} s ago"
    minutes = seconds / 60
    if minutes < 90:
        return f"{minutes:.0f} min ago"
    return f"{minutes / 60:.1f} h ago"


def _fmt_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"{seconds:.0f} s"
    minutes = seconds / 60
    if minutes < 90:
        return f"{minutes:.0f} min"
    return f"{minutes / 60:.1f} h"


def _fmt_ts(ts: float, tz: tzinfo) -> str:
    return datetime.fromtimestamp(ts, tz=tz).strftime("%Y-%m-%d %H:%M:%S %Z")


def _get_float(payload: dict[str, object], key: str, default: float) -> float:
    value = payload.get(key)
    return float(value) if isinstance(value, (int, float)) else default


def _get_int(payload: dict[str, object], key: str, default: int) -> int:
    value = payload.get(key)
    return int(value) if isinstance(value, (int, float)) else default


def _get_str(payload: dict[str, object], key: str, default: str) -> str:
    value = payload.get(key)
    return str(value) if value is not None else default


def _rows(pairs: list[tuple[str, str]]) -> str:
    return "".join(
        f'<tr><th scope="row">{escape(k)}</th><td>{escape(v)}</td></tr>' for k, v in pairs
    )


def render_status(
    payload: dict[str, object],
    aggregates: StatusAggregates,
    now: float,
    *,
    heartbeat_interval_s: float = DEFAULT_HEARTBEAT_INTERVAL_S,
    title: str = "Olive's Bark Logger — Local Status",
) -> str:
    """Render the full status snapshot as one self-contained HTML string.

    Pure function of (heartbeat payload, precomputed aggregates, wall-clock ``now``):
    the same inputs always yield the same HTML. No I/O, no network, no audio.
    """
    tz = aggregates.tz
    summary = aggregates.summary

    updated_at = _get_float(payload, "updated_at", now)
    age_s = now - updated_at
    stale = age_s > 3 * heartbeat_interval_s

    # --- header + freshness banner ---
    if stale:
        banner = (
            '<div class="note" role="alert">'
            f"<strong>Stale heartbeat.</strong> The monitor last checked in "
            f"{escape(_fmt_age(age_s))} ({escape(_fmt_ts(updated_at, tz))}), which is "
            f"longer than expected. It may have stopped — verify the service is "
            f"running.</div>"
        )
    else:
        banner = (
            '<p class="note">Heartbeat is fresh: the monitor last checked in '
            f"{escape(_fmt_age(age_s))}.</p>"
        )

    # --- live capture stats ---
    level = payload.get("last_level_dbfs")
    level_str = f"{float(level):.1f} dBFS" if isinstance(level, (int, float)) else "not reported"
    coverage = _get_float(payload, "frame_coverage", 1.0)
    frames_seen = _get_int(payload, "frames_seen", 0)
    frames_dropped = _get_int(payload, "frames_dropped", 0)
    uptime_s = _get_float(payload, "uptime_s", 0.0)
    live_rows = _rows(
        [
            ("Most recent level", level_str),
            ("Frames seen", f"{frames_seen:,}"),
            ("Frames dropped", f"{frames_dropped:,}"),
            ("Frame coverage", f"{coverage:.1%}"),
            ("Uptime", _fmt_age(uptime_s).replace(" ago", "")),
            ("Heartbeat", _fmt_age(age_s)),
            ("Status", _get_str(payload, "status", "unknown")),
        ]
    )
    live_table = (
        "<table><caption>Live capture</caption>"
        '<thead><tr><th scope="col">Metric</th><th scope="col">Value</th></tr></thead>'
        f"<tbody>{live_rows}</tbody></table>"
    )

    # --- monitoring gaps ---
    if aggregates.gaps is None:
        gaps_section = f'<p class="note">{escape(GAP_UNAVAILABLE_NOTE)}</p>'
    elif not aggregates.gaps:
        gaps_section = "<p>No monitoring gaps recorded in this window.</p>"
    else:
        items = "".join(f"<li>{escape(g)}</li>" for g in aggregates.gaps)
        gaps_section = f"<ul>{items}</ul>"

    # --- last night ---
    minutes_with_events = summary.total_loud_seconds / 60.0
    if aggregates.busiest_hour is None:
        loudest_window = "no events in window"
    else:
        h = aggregates.busiest_hour
        count = summary.by_hour.get(h, 0)
        loudest_window = f"{h:02d}:00–{(h + 1) % 24:02d}:00 ({count} events)"  # noqa: RUF001 - intentional en dash
    peak_str = (
        f"{summary.loudest_peak_dbfs:.1f} dBFS" if summary.event_count else "no events in window"
    )
    night_rows = _rows(
        [
            ("Events", f"{summary.event_count}"),
            ("Minutes with events", f"{minutes_with_events:.1f} min"),
            ("Busiest hour", loudest_window),
            ("Loudest peak", peak_str),
            (
                f"Events in quiet hours ({aggregates.quiet_window})",
                f"{summary.quiet_hours_event_count}",
            ),
            ("Loud time in quiet hours", f"{summary.quiet_hours_loud_seconds / 60.0:.1f} min"),
        ]
    )
    night_table = (
        f"<table><caption>Last {aggregates.window_hours} hours</caption>"
        '<thead><tr><th scope="col">Metric</th><th scope="col">Value</th></tr></thead>'
        f"<tbody>{night_rows}</tbody></table>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>{escape(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<a class="skip" href="#main">Skip to status</a>
<main id="main">
<h1>{escape(title)}</h1>
<p>Snapshot as of <strong>{escape(_fmt_ts(now, tz))}</strong> (time zone
<strong>{escape(aggregates.tz_name)}</strong>). This page is a static file the monitor
rewrites in place; open it directly from disk. No server, no network, no audio.</p>
{banner}

<h2>Live capture</h2>
{live_table}

<h2>Monitoring gaps</h2>
{gaps_section}

<h2>Last night</h2>
<p>Summary of the most recent {aggregates.window_hours} hours of logged events. Counts
are sound-level events (a threshold crossing held long enough) — never audio.</p>
{night_table}
</main>
</body>
</html>
"""


def write_status(path: str | Path, html: str) -> None:
    """Atomically write ``status.html`` (temp file + os.replace), mirroring
    ``monitor.health.write_health`` so a reader never sees a half-written page and a
    crash mid-write cannot corrupt it."""
    target = Path(path)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(html, encoding="utf-8")
    os.replace(tmp, target)
