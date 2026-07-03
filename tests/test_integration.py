"""End-to-end: synthetic frames -> level -> detector -> SQLite -> report.

Also asserts the only file the pipeline creates is the SQLite database — there is no
audio artifact left on disk anywhere.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from monitor.capture import LoudRegion, resilient_source, synthetic_session
from monitor.config import Config
from monitor.service import run_pipeline
from report.render import generate_report_from_db
from store import EventStore


def test_full_pipeline_logs_events_and_renders_report(tmp_path):
    db = tmp_path / "olive.db"
    config = Config(db_path=str(db))
    labels = [LoudRegion(2.0, 5.0, 0.3), LoudRegion(10.0, 12.0, 0.4)]

    with EventStore(db) as store:
        events = list(
            run_pipeline(
                synthetic_session(15.0, labels, frame_size=config.frame_size), config, store
            )
        )
        assert len(events) == 2
        stored = store.events()
    assert len(stored) == 2

    html = generate_report_from_db(str(db), config, generated_at="2026-01-01 00:00 UTC")
    assert "Total events" in html
    assert "<h2>Methodology</h2>" in html

    # The only file produced is the database (plus possible -journal/-wal). No audio.
    produced = {p.name for p in tmp_path.iterdir()}
    for name in produced:
        assert name.startswith("olive.db"), f"unexpected artifact: {name}"
    audio_ext = (".wav", ".pcm", ".raw", ".aiff", ".flac", ".mp3", ".ogg")
    assert not any(Path(n).suffix in audio_ext for n in produced)


def test_calibration_persisted_and_reflected_in_report(tmp_path):
    db = tmp_path / "olive.db"
    config = Config(db_path=str(db), calibration_offset=9.0, calibration_note="bench cal")
    with EventStore(db) as store:
        store.set_calibration(config.calibration_offset, config.calibration_note)
    html = generate_report_from_db(str(db), config, generated_at="2026-01-01 00:00 UTC")
    assert "+9.0 dB" in html
    assert "bench cal" in html


def test_source_killed_mid_session_records_gap_shown_in_report(tmp_path):
    """Kill the synthetic source mid-session; the outage is persisted as a gap and the
    generated report renders it as 'not monitored', distinct from a quiet hour."""
    db = tmp_path / "olive.db"
    config = Config(db_path=str(db), tz="UTC")
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp()
    loud = [0.3] * 10  # ~-10 dBFS, well above the -35 threshold
    quiet = [0.0005] * 10  # ~-66 dBFS, below threshold

    invocations = {"n": 0}

    def make_source():
        invocations["n"] += 1
        if invocations["n"] == 1:
            t0 = base + 1 * 3600  # an event in hour 01
            for i in range(8):
                yield (t0 + i * 0.1, loud)
            for i in range(12):  # quiet long enough to close the event (>debounce)
                yield (t0 + 0.8 + i * 0.1, quiet)
            raise OSError("mic unplugged")  # device dies mid-session
        t1 = base + 20 * 3600  # a second event in hour 20 after recovery
        for i in range(8):
            yield (t1 + i * 0.1, loud)

    # A fake wall clock places the outage inside hour 10 (which has no events):
    # first read is the outage start, second (and later) is the recovery time.
    ticks = [base + 10 * 3600, base + 10 * 3600 + 1800]

    def clock():
        return ticks.pop(0) if len(ticks) > 1 else ticks[0]

    with EventStore(db) as store:
        source = resilient_source(
            make_source,
            sleep=lambda _: None,
            on_gap=lambda s, e, r: store.add_gap(s, e, r),
            clock=clock,
        )
        events = list(run_pipeline(source, config, store))
        assert len(events) == 2  # one before, one after the outage
        gaps = store.gaps()
        assert len(gaps) == 1
        assert gaps[0].reason == "device-error"

    html = generate_report_from_db(str(db), config, generated_at="2026-01-01 00:00 UTC")
    assert "not monitored" in html  # the gap is rendered, not read as quiet
    assert "wall-clock hours" in html  # methodology states monitored vs wall-clock
