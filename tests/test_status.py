"""The static local status page: content, freshness banner, atomic write, a11y, no egress.

Mirrors the conventions of tests/test_a11y.py (structural WCAG floor) and
tests/test_no_egress.py (local-only) for the status snapshot rendered by report/status.py.
"""

from __future__ import annotations

import re

from monitor.config import Config
from monitor.detector import Event
from monitor.service import _write_status_page
from report.aggregate import summarize
from report.status import (
    GAP_UNAVAILABLE_NOTE,
    StatusAggregates,
    collect_status_aggregates,
    render_status,
    write_status,
)
from store import EventStore

START = 1_767_312_000.0  # a fixed instant so every render is deterministic


def _payload(updated_at: float = START, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "session_id": 1,
        "started_at": updated_at - 3600,
        "updated_at": updated_at,
        "uptime_s": 3600.0,
        "frames_seen": 900,
        "frames_dropped": 100,
        "frame_coverage": 0.9,
        "db_path": "olive.db",
        "version": "test",
        "last_level_dbfs": -12.3,
    }
    payload.update(overrides)
    return payload


def _aggregates(events: list[Event] | None = None, **overrides: object) -> StatusAggregates:
    config = Config()
    summary = summarize(events or [], quiet_hours=config.quiet_hours)
    busiest = None
    if summary.by_hour and any(summary.by_hour.values()):
        busiest = max(summary.by_hour, key=lambda h: summary.by_hour[h])
    base: dict[str, object] = {
        "summary": summary,
        "quiet_window": "22:00–08:00",  # noqa: RUF001 - intentional en dash
        "tz_name": "UTC",
        "busiest_hour": busiest,
        "gaps": None,
    }
    base.update(overrides)
    return StatusAggregates(**base)


def _events(n: int = 3) -> list[Event]:
    return [
        Event(
            start=START + i * 3600,
            end=START + i * 3600 + 4,
            duration=4.0,
            peak_level=-9.0 - i,
            avg_level=-13.0,
        )
        for i in range(n)
    ]


def _html(**overrides: object) -> str:
    return render_status(_payload(), _aggregates(_events()), now=START, **overrides)


# --- required sections / content ------------------------------------------------


def test_renders_all_required_sections():
    html = _html()
    for heading in ("Live capture", "Monitoring gaps", "Last night"):
        assert f"<h2>{heading}</h2>" in html


def test_live_stats_show_level_coverage_and_frames():
    html = _html()
    assert "-12.3 dBFS" in html  # most recent level from the payload
    assert "90.0%" in html  # frame coverage 0.9
    assert "900" in html and "100" in html  # frames seen / dropped


def test_last_night_summary_present():
    html = _html()
    assert "Events" in html
    assert "Busiest hour" in html
    assert "Loudest peak" in html


def test_gap_ledger_absent_renders_unavailable_state():
    html = _html()
    assert GAP_UNAVAILABLE_NOTE in html


def test_gap_ledger_present_lists_gaps():
    html = render_status(
        _payload(),
        _aggregates(_events(), gaps=["2026-01-01 02:00–02:30 (monitor down)"]),  # noqa: RUF001
        now=START,
    )
    assert "monitor down" in html
    assert GAP_UNAVAILABLE_NOTE not in html


def test_level_not_reported_when_absent():
    payload = _payload()
    del payload["last_level_dbfs"]
    html = render_status(payload, _aggregates(_events()), now=START)
    assert "not reported" in html


# --- heartbeat freshness --------------------------------------------------------


def test_stale_heartbeat_warning_appears_when_old():
    # updated 10 minutes ago, well past 3x the 60s nominal interval.
    payload = _payload(updated_at=START - 600)
    html = render_status(payload, _aggregates(_events()), now=START)
    assert 'role="alert"' in html
    assert "Stale heartbeat" in html


def test_fresh_heartbeat_has_no_stale_warning():
    html = _html()
    assert 'role="alert"' not in html
    assert "Heartbeat is fresh" in html


# --- store integration ----------------------------------------------------------


def test_collect_status_aggregates_from_store(tmp_path):
    config = Config(db_path=str(tmp_path / "olive.db"))
    with EventStore(config.db_path) as store:
        for ev in _events(3):
            store.add_event(ev)
        agg = collect_status_aggregates(store, config, now=START + 3 * 3600 + 100)
    assert agg.summary.event_count == 3
    assert agg.busiest_hour is not None
    assert agg.gaps == []
    html = render_status(_payload(), agg, now=START + 3 * 3600 + 100)
    assert "<h1>" in html


def test_collect_status_aggregates_empty_store(tmp_path):
    config = Config(db_path=str(tmp_path / "olive.db"))
    with EventStore(config.db_path) as store:
        agg = collect_status_aggregates(store, config, now=START)
    assert agg.summary.event_count == 0
    assert agg.busiest_hour is None
    # Renders without error even with nothing logged.
    assert "no events in window" in render_status(_payload(), agg, now=START)


def test_collect_status_aggregates_lists_recorded_gaps(tmp_path):
    config = Config(db_path=str(tmp_path / "olive.db"))
    with EventStore(config.db_path) as store:
        store.add_gap(START - 600, START - 300, "device-error")
        agg = collect_status_aggregates(store, config, now=START)
    assert agg.gaps is not None and len(agg.gaps) == 1
    assert "5 min" in agg.gaps[0]
    assert "device error" in agg.gaps[0]


def test_status_page_can_be_enabled_without_health_file(tmp_path):
    path = tmp_path / "status.html"
    config = Config(db_path=str(tmp_path / "olive.db"), status_path=str(path))
    with EventStore(config.db_path) as store:
        _write_status_page(config, store, _payload())
    assert path.exists()
    assert "Local Status" in path.read_text(encoding="utf-8")


# --- atomic write ---------------------------------------------------------------


def test_write_status_leaves_no_tmp_file(tmp_path):
    path = tmp_path / "status.html"
    write_status(path, _html())
    assert path.exists()
    assert not (tmp_path / "status.html.tmp").exists()


def test_write_status_overwrites(tmp_path):
    path = tmp_path / "status.html"
    write_status(path, "<html>one</html>")
    write_status(path, "<html>two</html>")
    assert "two" in path.read_text(encoding="utf-8")


# --- accessibility (structural floor, mirrors test_a11y.py) ---------------------


def test_has_lang_attribute():
    assert '<html lang="en">' in _html()


def test_has_viewport_meta():
    assert 'name="viewport"' in _html()


def test_exactly_one_h1():
    assert _html().count("<h1>") == 1


def test_has_skip_link_and_main_landmark():
    html = _html()
    assert 'class="skip"' in html and 'href="#main"' in html
    assert 'id="main"' in html
    assert "<main" in html


def test_tables_use_scoped_headers():
    html = _html()
    assert 'scope="col"' in html and 'scope="row"' in html


def test_every_table_has_a_caption():
    html = _html()
    tables = re.findall(r"<table>.*?</table>", html, re.DOTALL)
    assert tables
    for table in tables:
        assert "<caption>" in table


def test_respects_reduced_motion_and_focus_visible():
    html = _html()
    assert "prefers-reduced-motion" in html
    assert ":focus-visible" in html


# --- local-only / no egress -----------------------------------------------------


def test_no_external_references_in_html():
    html = _html()
    assert "://" not in html  # no absolute URLs to any host
    assert "src=" not in html  # no external scripts/images
    assert 'href="http' not in html
