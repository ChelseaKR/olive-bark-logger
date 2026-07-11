"""Clock-integrity guard: divergence detection, store round-trip, report disclosure."""

from __future__ import annotations

from datetime import datetime, timezone

from monitor.clock import BACKWARD_JUMP, FORWARD_JUMP, ClockGuard
from monitor.config import Config
from report.aggregate import describe_clock_anomalies, summarize
from report.render import NO_CLOCK_ANOMALY_NOTE, build_report
from store import EventStore


def test_forward_wall_jump_is_detected_with_correct_delta_and_direction():
    # Baseline at wall=1000, mono=500. Monotonic advances a steady 10 s while the wall
    # clock lurches forward by 2 hours (NTP sync on a fresh Pi).
    guard = ClockGuard(wall0=1000.0, mono0=500.0, tolerance_s=2.0)
    now_mono = 510.0
    now_wall = 1000.0 + 10.0 + 7200.0  # 10 s of real time plus a 2-hour jump
    anomaly = guard.check(now_wall, now_mono)
    assert anomaly is not None
    assert anomaly.kind == FORWARD_JUMP
    assert anomaly.delta == 7200.0  # drift = wall_elapsed - mono_elapsed
    assert anomaly.wall_after == now_wall
    assert anomaly.wall_before == 1010.0  # wall expected from monotonic progression only


def test_backward_wall_jump_is_detected():
    guard = ClockGuard(wall0=2000.0, mono0=100.0, tolerance_s=2.0)
    # Monotonic advances 5 s; wall goes backward by ~1 hour.
    anomaly = guard.check(2000.0 + 5.0 - 3600.0, 105.0)
    assert anomaly is not None
    assert anomaly.kind == BACKWARD_JUMP
    assert anomaly.delta == -3600.0


def test_clean_run_reports_no_anomalies():
    # Wall and monotonic advance together in lockstep — no divergence at any check.
    guard = ClockGuard(wall0=0.0, mono0=0.0, tolerance_s=2.0)
    for step in (1.0, 2.0, 100.0, 3600.0):
        assert guard.check(step, step) is None


def test_tolerance_boundary():
    # Exactly at tolerance is not an anomaly; just beyond it is.
    at = ClockGuard(wall0=0.0, mono0=0.0, tolerance_s=2.0)
    assert at.check(12.0, 10.0) is None  # drift == 2.0 (<= tolerance)
    over = ClockGuard(wall0=0.0, mono0=0.0, tolerance_s=2.0)
    assert over.check(12.001, 10.0) is not None  # drift just over tolerance


def test_rebaselines_so_one_jump_is_reported_once():
    guard = ClockGuard(wall0=0.0, mono0=0.0, tolerance_s=2.0)
    # A single 100 s forward jump at the first check.
    first = guard.check(101.0, 1.0)
    assert first is not None and first.delta == 100.0
    # Steady progress afterward: monotonic and wall both advance 5 s. No new anomaly.
    assert guard.check(106.0, 6.0) is None


def test_store_round_trip_add_and_query_clock_anomaly(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        sid = store.start_session(
            started_at=0.0,
            device_label="pi-1",
            mic_model="",
            placement_note="",
            tz="UTC",
            calibration_offset=0.0,
            calibration_note="x",
            app_version="0.1.0",
        )
        store.add_clock_anomaly(
            session_id=sid,
            kind=FORWARD_JUMP,
            wall_before=1010.0,
            wall_after=8210.0,
            delta=7200.0,
            detected_at=8210.0,
        )
        # Out-of-window row (earlier) to prove the window filter works.
        store.add_clock_anomaly(
            session_id=sid,
            kind=BACKWARD_JUMP,
            wall_before=50.0,
            wall_after=10.0,
            delta=-40.0,
            detected_at=10.0,
        )

        all_rows = store.clock_anomalies()
        assert len(all_rows) == 2
        assert all_rows[0].detected_at == 10.0  # ordered by detection time

        windowed = store.clock_anomalies(start=1000.0, end=9000.0)
        assert len(windowed) == 1
        row = windowed[0]
        assert row.kind == FORWARD_JUMP
        assert row.session_id == sid
        assert row.delta == 7200.0
        assert row.wall_after == 8210.0


def test_describe_clock_anomalies_formats_direction_and_delta(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        store.add_clock_anomaly(
            session_id=None,
            kind=FORWARD_JUMP,
            wall_before=1010.0,
            wall_after=8210.0,
            delta=7200.0,
            detected_at=8210.0,
        )
        lines = describe_clock_anomalies(store.clock_anomalies(), tz=timezone.utc)
    assert len(lines) == 1
    assert "forward" in lines[0] and "7200.0 s" in lines[0]


def _report_with_anomaly_lines(lines):
    config = Config(tz="UTC")
    summary = summarize([], quiet_hours=config.quiet_hours, tz=config.tzinfo())
    return build_report(
        summary,
        config=config,
        generated_at="2026-01-01 00:00 UTC",
        clock_anomaly_lines=lines,
    )


def test_report_discloses_no_anomalies_by_default():
    assert NO_CLOCK_ANOMALY_NOTE in _report_with_anomaly_lines([])


def test_report_discloses_anomaly_line_when_present():
    dt = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
    line = f"Clock jumped forward by 7200.0 s (wall time X → {dt:%Y-%m-%d %H:%M:%S})."
    html = _report_with_anomaly_lines([line])
    assert "Clock jumped forward by 7200.0 s" in html
    assert NO_CLOCK_ANOMALY_NOTE not in html
