"""Merge-blocking: the report is reproducible — same event log, byte-identical HTML.

Two guarantees: (1) building the same fixture twice is byte-identical (determinism),
and (2) it matches the committed golden in tests/snapshots/report.html. If a rendering
change is intentional, regenerate the golden with: make snapshot.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from monitor.config import Config
from monitor.detector import Event
from report.aggregate import summarize
from report.render import build_report

GOLDEN = Path(__file__).resolve().parent / "snapshots" / "report.html"


def fixture_html() -> str:
    """A fixed, machine-independent report used for snapshotting."""
    config = Config(tz="UTC")
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp()
    spec = [(23, 6.0, -8.0), (23, 4.0, -12.0), (2, 9.0, -5.0), (14, 3.0, -20.0)]
    events = [
        Event(
            start=base + hour * 3600,
            end=base + hour * 3600 + dur,
            duration=dur,
            peak_level=peak,
            avg_level=peak - 4.0,
        )
        for hour, dur, peak in spec
    ]
    summary = summarize(events, quiet_hours=config.quiet_hours, tz=config.tzinfo())
    return build_report(summary, config=config, generated_at="2026-01-01 12:00 UTC")


def test_report_is_deterministic():
    assert fixture_html() == fixture_html()


def test_report_matches_golden():
    assert GOLDEN.exists(), "golden missing; run `make snapshot` to create it"
    assert fixture_html() == GOLDEN.read_text(encoding="utf-8")
