"""Calibration math, the level meter, and the calibrate CLI."""

from __future__ import annotations

from monitor.calibrate import (
    compute_offset,
    main_calibrate,
    measure_levels,
    meter_bar,
    suggest_threshold,
)
from monitor.capture import LoudRegion, synthetic_session
from monitor.level import SILENCE_FLOOR_DBFS
from store import EventStore


def test_compute_offset():
    assert compute_offset(measured_dbfs=-50.0, reference_spl_db=60.0) == 110.0


def test_suggest_threshold_uses_median_plus_margin():
    assert suggest_threshold([-40, -40, -40], margin_db=6.0) == -34.0


def test_suggest_threshold_empty():
    assert suggest_threshold([], margin_db=6.0) == SILENCE_FLOOR_DBFS + 6.0


def test_meter_bar_clamps():
    assert meter_bar(10.0, width=10).startswith("[##########]")  # above ceil -> full
    assert meter_bar(-200.0, width=10).startswith("[----------]")  # below floor -> empty


def test_meter_bar_midscale():
    bar = meter_bar(-30.0, floor=-60.0, ceil=0.0, width=10)
    assert bar.startswith("[#####-----]")


def test_measure_levels_respects_cap():
    source = synthetic_session(10.0, [LoudRegion(0.0, 10.0, 0.3)], frame_size=1600)
    levels = measure_levels(source, max_frames=5)
    assert len(levels) == 5
    assert all(lvl > -20 for lvl in levels)  # loud tone is well above silence


def test_main_calibrate_stores_offset(tmp_path, capsys):
    db = tmp_path / "olive.db"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(f'{{"db_path": "{db}"}}')

    def factory(config):
        return synthetic_session(3.0, [LoudRegion(0.0, 3.0, 0.3)], frame_size=config.frame_size)

    rc = main_calibrate(
        ["--config", str(cfg), "--reference-db", "70", "--seconds", "2"], source_factory=factory
    )
    assert rc == 0
    assert "offset" in capsys.readouterr().out

    with EventStore(db) as store:
        calib = store.get_calibration()
    assert calib is not None
    offset, note = calib
    # measured ~ -10.5 dBFS for amplitude 0.3, so offset ~ 70 - (-10.5) = ~80.5
    assert 75.0 < offset < 86.0
    assert "70.0 dB" in note
    # Provenance not supplied -> recorded as not recorded.
    assert "Reference instrument not recorded" in note


def test_main_calibrate_records_reference_instrument(tmp_path, capsys):
    # R2: the reference-instrument provenance is stored in the calibration note so a
    # reader knows what the offset was measured against.
    db = tmp_path / "olive.db"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(f'{{"db_path": "{db}"}}')

    def factory(config):
        return synthetic_session(3.0, [LoudRegion(0.0, 3.0, 0.3)], frame_size=config.frame_size)

    rc = main_calibrate(
        [
            "--config",
            str(cfg),
            "--reference-db",
            "70",
            "--seconds",
            "2",
            "--reference-instrument",
            "Brand X, IEC 61672 Class 2",
        ],
        source_factory=factory,
    )
    assert rc == 0
    with EventStore(db) as store:
        _offset, note = store.get_calibration()
    assert "Reference instrument: Brand X, IEC 61672 Class 2." in note
