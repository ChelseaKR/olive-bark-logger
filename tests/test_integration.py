"""End-to-end: synthetic frames -> level -> detector -> SQLite -> report.

Also asserts the only file the pipeline creates is the SQLite database — there is no
audio artifact left on disk anywhere.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from monitor.capture import LoudRegion, resilient_source, synthetic_session
from monitor.config import Config
from monitor.detector import Event
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
    config = Config(db_path=str(db))
    with EventStore(db) as store:
        store.add_calibration(9.0, "bench cal", effective_from=0.0)
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


def test_calibrate_then_monitor_then_report_applies_offset_at_render_only(tmp_path):
    """Round-trip: calibrate -> monitor -> report. Events store raw dBFS; the offset is
    applied only at render time, and monitor never overwrites the stored calibration."""
    from monitor.calibrate import main_calibrate

    db = tmp_path / "olive.db"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(f'{{"db_path": "{db}", "threshold_dbfs": -35.0}}')
    config = Config.load(cfg)

    # 1) Calibrate: measure a steady 0.3-amplitude tone against a 70 dB reference.
    def cal_factory(c):
        return synthetic_session(3.0, [LoudRegion(0.0, 3.0, 0.3)], frame_size=c.frame_size)

    assert (
        main_calibrate(
            ["--config", str(cfg), "--reference-db", "70", "--seconds", "2"],
            source_factory=cal_factory,
        )
        == 0
    )
    with EventStore(db) as store:
        cal = store.get_calibration()
    assert cal is not None
    offset = cal[0]

    # 2) Monitor: log events. Levels are persisted RAW (no offset baked in).
    with EventStore(db) as store:
        events = list(
            run_pipeline(
                synthetic_session(6.0, [LoudRegion(1.0, 4.0, 0.4)], frame_size=config.frame_size),
                config,
                store,
            )
        )
        assert events
        raw_peak = max(e.peak_level for e in events)
        stored_peak = max(e.peak_level for e in store.events())
        # Monitor did not rewrite calibration, and stored levels are raw (well below SPL).
        assert store.get_calibration() == cal
        assert stored_peak == raw_peak
        assert stored_peak < 0.0  # raw dBFS, not the ~+70 dB SPL-adjusted value

    # 3) Report: the offset shows up only now, applied at render.
    html = generate_report_from_db(str(db), config, generated_at="2026-01-01 00:00 UTC")
    assert f"{offset:+.1f} dB" in html
    # The loudest peak in the summary reflects raw + offset, i.e. approximate SPL.
    assert f"{raw_peak + offset:.1f} dBFS" in html


def test_report_spanning_recalibration_shows_both_epochs(tmp_path):
    """A reporting window that straddles a recalibration discloses both epochs and
    applies each event's own offset — re-rendering old dates never changes with new cal."""
    db = tmp_path / "olive.db"
    config = Config(db_path=str(db), tz="UTC")

    with EventStore(db) as store:
        # Two calibration epochs: +5 dB from the start, +12 dB from t=1000.
        store.add_calibration(5.0, "first cal", effective_from=0.0)
        store.add_calibration(
            12.0, "second cal", reference_instrument="Bruel-Kjaer 2250", effective_from=1000.0
        )
        # One raw event under each epoch (raw peak -8 dBFS both).
        store.add_event(Event(500.0, 504.0, 4.0, -8.0, -12.0))  # epoch 1 -> +5
        store.add_event(Event(1500.0, 1504.0, 4.0, -8.0, -12.0))  # epoch 2 -> +12

    html = generate_report_from_db(str(db), config, generated_at="2026-01-01 00:00 UTC")

    # Both epoch offsets are disclosed in the per-epoch table.
    assert "+5.0 dB" in html
    assert "+12.0 dB" in html
    assert "more than one calibration epoch" in html
    assert "Calibration offsets by epoch" in html
    assert "Bruel-Kjaer 2250" in html
    # The loudest peak reflects the later epoch's larger offset applied to a raw -8 dBFS.
    assert f"{-8.0 + 12.0:.1f} dBFS" in html
