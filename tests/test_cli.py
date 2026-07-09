"""CLI entrypoints and a few store/chart edge cases (coverage of the real surface)."""

from __future__ import annotations

import json

import monitor.capture_live as capture_live
import pytest
from monitor.capture import LoudRegion, synthetic_session
from monitor.config import Config
from monitor.detector import Event
from monitor.service import main as monitor_main
from report.charts import bar_chart
from report.render import main as report_main
from store import EventStore


def test_monitor_main_runs_with_a_fake_source(tmp_path, monkeypatch, capsys):
    db = tmp_path / "olive.db"
    health = tmp_path / "health.json"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(
        json.dumps(
            {
                "db_path": str(db),
                "min_duration_s": 0.4,
                "health_path": str(health),
                "placement_note": "test bench",
            }
        )
    )

    def fake_live_source(sample_rate=16000, frame_size=1600, stats=None):
        # Count frames the way the real source would, so coverage is exercised.
        yield from synthetic_session(8.0, [LoudRegion(1.0, 4.0, 0.4)], frame_size=frame_size)

    monkeypatch.setattr(capture_live, "live_source", fake_live_source)
    rc = monitor_main(["--config", str(cfg)], now=1000.0)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Monitoring" in out and "event @" in out

    with EventStore(db) as store:
        assert len(store.events()) == 1
        session = store.latest_session()
    assert session is not None
    assert session.placement_note == "test bench"
    assert session.frames_seen > 0
    assert session.ended_at == 1000.0

    # Heartbeat file was written and is valid JSON with coverage.
    payload = json.loads(health.read_text())
    assert payload["frame_coverage"] == 1.0
    assert payload["frames_seen"] == session.frames_seen


def test_monitor_main_prunes_per_retention(tmp_path, monkeypatch, capsys):
    db = tmp_path / "olive.db"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"db_path": str(db), "retention_days": 1}))

    # Seed an event with a distinctive old timestamp the detector won't reproduce.
    ancient = 0.5
    with EventStore(db) as store:
        store.add_event(Event(ancient, ancient + 1, 1.0, -10.0, -14.0))

    def fake_live_source(sample_rate=16000, frame_size=1600, stats=None):
        yield from synthetic_session(6.0, [LoudRegion(1.0, 4.0, 0.4)], frame_size=frame_size)

    monkeypatch.setattr(capture_live, "live_source", fake_live_source)
    monitor_main(["--config", str(cfg)], now=1_000_000.0)
    assert "Retention: pruned 1" in capsys.readouterr().out

    with EventStore(db) as store:
        starts = [e.start for e in store.events()]
    assert ancient not in starts  # the ancient event was pruned
    assert starts  # newly detected events (added after prune) survive


def test_monitor_main_does_not_clobber_stored_calibration(tmp_path, monkeypatch, capsys):
    """Regression for FIX-01: `olive-calibrate` then `olive-monitor` (default config)
    must not revert the device to uncalibrated. The monitor reads calibration; it never
    writes it, and the session records the *stored* offset, not the config default."""
    db = tmp_path / "olive.db"
    cfg = tmp_path / "cfg.json"
    # Default config -> calibration_offset 0.0; the stored calibration must win.
    cfg.write_text(json.dumps({"db_path": str(db)}))

    with EventStore(db) as store:
        store.add_calibration(6.5, "bench cal", reference_instrument="B&K 2250", effective_from=0.0)

    def fake_live_source(sample_rate=16000, frame_size=1600, stats=None):
        yield from synthetic_session(6.0, [LoudRegion(1.0, 4.0, 0.4)], frame_size=frame_size)

    monkeypatch.setattr(capture_live, "live_source", fake_live_source)
    assert monitor_main(["--config", str(cfg)], now=1000.0) == 0
    capsys.readouterr()

    with EventStore(db) as store:
        # Calibration is untouched: still exactly one epoch with the original offset.
        assert len(store.calibration_history()) == 1
        assert store.get_calibration() == (6.5, "bench cal")
        session = store.latest_session()
    assert session is not None
    assert session.calibration_offset == 6.5  # sourced from the store, not the config
    assert session.calibration_note == "bench cal"


def test_report_main_writes_file(tmp_path, capsys):
    db = tmp_path / "olive.db"
    out = tmp_path / "r.html"
    config = Config(db_path=str(db))
    with EventStore(db) as store:
        store.add_calibration(0.0, config.calibration_note, effective_from=0.0)
        store.add_event(Event(1_767_312_000.0, 1_767_312_004.0, 4.0, -8.0, -12.0))
    rc = report_main(["--db", str(db), "--out", str(out), "--generated-at", "2026-01-01 UTC"])
    assert rc == 0
    assert out.exists()
    assert "<h2>Methodology</h2>" in out.read_text()
    assert "Wrote" in capsys.readouterr().out


def test_report_exports_apply_render_time_calibration(tmp_path, capsys):
    """Regression (FIX-01 review finding 1): --csv/--violations-csv/--violations-html
    must carry the same render-time calibration as the HTML report, with the calibrated
    flag derived from the store's history — not the deprecated config field. Pre-fix,
    the exports emitted unadjusted levels, so on a calibrated device they disagreed
    numerically with the report and the violations HTML misstated the calibration."""
    import csv as csv_mod

    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        store.add_calibration(6.5, "bench cal", effective_from=0.0)
        # One event during quiet hours, raw peak -8.0 / avg -12.0 dBFS.
        start = 1_767_326_400.0  # 2026-01-02T04:00:00Z
        store.add_event(Event(start, start + 4.0, 4.0, -8.0, -12.0))
    cfg = tmp_path / "cfg.json"
    # Config calibration_offset stays 0.0 — the store's history must win everywhere.
    cfg.write_text(json.dumps({"db_path": str(db), "tz": "UTC"}))

    out = tmp_path / "r.html"
    csv_out = tmp_path / "events.csv"
    vcsv = tmp_path / "v.csv"
    vhtml = tmp_path / "v.html"
    args = ["--config", str(cfg), "--db", str(db), "--out", str(out), "--csv", str(csv_out)]
    args += ["--violations-csv", str(vcsv), "--violations-html", str(vhtml)]
    args += ["--generated-at", "2026-01-01 UTC"]
    rc = report_main(args)
    assert rc == 0
    capsys.readouterr()

    # The HTML report applies +6.5 at render: raw peak -8.0 -> -1.5.
    assert "-1.5 dBFS" in out.read_text()

    # The event CSV agrees numerically and records the offset it applied per row.
    rows = list(csv_mod.reader(csv_out.read_text().splitlines()))
    assert rows[1][rows[0].index("peak_dbfs")] == "-1.5"
    assert rows[1][rows[0].index("calibration_offset_db")] == "+6.5"

    # The violations CSV agrees too.
    vrows = list(csv_mod.reader(vcsv.read_text().splitlines()))
    assert vrows[1][vrows[0].index("peak_dbfs")] == "-1.5"
    assert vrows[1][vrows[0].index("calibration_offset_db")] == "+6.5"

    # The violations HTML derives its calibration statement from the store, not config.
    vh = vhtml.read_text()
    assert "A calibration offset is applied" in vh
    assert "No calibration offset is applied" not in vh
    assert "-1.5" in vh


def test_store_time_window_filters(tmp_path):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for t in (100.0, 200.0, 300.0):
            store.add_event(Event(t, t + 1, 1.0, -10.0, -14.0))
        assert len(store.events(since=150, until=250)) == 1
        assert len(store.events(since=150)) == 2
        assert len(store.events(until=250)) == 2


def test_get_calibration_none_when_unset(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        assert store.get_calibration() is None


def test_bar_chart_length_mismatch_raises():
    with pytest.raises(ValueError):
        bar_chart(chart_id="x", title="t", labels=["a"], values=[1.0, 2.0], value_caption="n")


def test_bar_chart_handles_all_zero_values():
    html = bar_chart(
        chart_id="z", title="Zeros", labels=["a", "b"], values=[0.0, 0.0], value_caption="events"
    )
    assert "<svg" in html and "<table" in html


def test_config_to_dict_roundtrips_quiet_hours():
    d = Config().to_dict()
    assert d["quiet_hours"]["start_hour"] == 22
