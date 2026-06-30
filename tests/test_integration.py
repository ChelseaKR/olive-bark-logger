"""End-to-end: synthetic frames -> level -> detector -> SQLite -> report.

Also asserts the only file the pipeline creates is the SQLite database — there is no
audio artifact left on disk anywhere.
"""

from __future__ import annotations

from pathlib import Path

from monitor.capture import LoudRegion, synthetic_session
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
