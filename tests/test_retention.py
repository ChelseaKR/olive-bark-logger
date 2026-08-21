"""Retention reaches every table it should, and says what it reached.

Issue #51: `retention_days` deleted rows from `events` and nothing else, so the ambient
minute ledger (EXP-01) — the one continuous dataset in the store, 1,440 rows a day
about the inside of a home — was kept forever, along with every gap, clock anomaly, and
session row older than the horizon. The operator line said "pruned N event(s)" and a
reader took that for the store. Minimal retention was the one privacy commitment of the
three (no audio, no egress, minimal retention) enforced by prose rather than a test.

Three things are held here:

1. Every table in the live schema is either pruned or on the explicit exemption list
   with a stated reason, so a new table cannot sit outside the policy unnoticed.
2. The ambient ledger is actually pruned by the monitor's real startup path, not just
   by calling `prune()` directly.
3. The session rule errs toward keeping: a crashed run with no `ended_at` is kept for
   as long as its frame counters prove it was listening, and a session still referenced
   by a retained row is never deleted from under it.
"""

from __future__ import annotations

import json
import sqlite3

import monitor.capture_live as capture_live
from monitor.ambient import MinuteLevel
from monitor.capture import LoudRegion, synthetic_session
from monitor.detector import Event
from monitor.service import main as monitor_main
from store import PRUNED_TABLES, RETENTION_EXEMPT_TABLES, EventStore

DAY = 86400.0
HORIZON = 1_000_000.0  # unix seconds; "older than" means strictly before this


def _ev(start: float) -> Event:
    return Event(start, start + 2.0, 2.0, -10.0, -14.0)


def _minute(start: float) -> MinuteLevel:
    return MinuteLevel(
        minute_start=start,
        min_dbfs=-60.0,
        median_dbfs=-50.0,
        max_dbfs=-30.0,
        l90_dbfs=-55.0,
        frame_count=600,
    )


def _session(store: EventStore, started_at: float, *, frames: int = 0) -> int:
    return store.start_session(
        started_at=started_at,
        device_label="pi-1",
        mic_model="USB mic",
        placement_note="by the wall",
        tz="UTC",
        calibration_offset=0.0,
        calibration_note="none",
        app_version="test",
        sample_rate=16000,
        frame_size=1600,
    )


# --- 1. the schema cannot outgrow the policy --------------------------------------


def test_every_table_is_either_pruned_or_explicitly_exempt(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        live = {
            r[0] for r in store._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    covered = set(PRUNED_TABLES) | set(RETENTION_EXEMPT_TABLES)
    unaccounted = live - covered
    assert not unaccounted, (
        f"tables outside the retention policy: {sorted(unaccounted)} — add each to "
        "EventStore.prune or to RETENTION_EXEMPT_TABLES with a reason"
    )
    # And the lists describe the real schema, not a remembered one.
    assert set(PRUNED_TABLES) <= live
    assert set(RETENTION_EXEMPT_TABLES) <= live
    assert all(RETENTION_EXEMPT_TABLES.values()), "every exemption states its reason"


def test_prune_reaches_every_time_keyed_table_and_reports_each(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        old_sid = _session(store, HORIZON - 3 * DAY, frames=0)
        store.update_session(old_sid, frames_seen=100, frames_dropped=0, ended_at=HORIZON - 2 * DAY)
        new_sid = _session(store, HORIZON + DAY)

        store.add_event(_ev(HORIZON - DAY), session_id=old_sid)
        store.add_event(_ev(HORIZON + DAY), session_id=new_sid)
        for i in range(3):
            store.add_minute_level(_minute(HORIZON - DAY + 60 * i), session_id=old_sid)
        store.add_minute_level(_minute(HORIZON + DAY), session_id=new_sid)
        store.add_gap(HORIZON - DAY, HORIZON - DAY + 600, "device-error", session_id=old_sid)
        store.add_gap(HORIZON - 300, HORIZON + 300, "device-error", session_id=new_sid)  # straddles
        store.add_clock_anomaly(
            session_id=old_sid,
            kind="forward-jump",
            wall_before=HORIZON - DAY,
            wall_after=HORIZON - DAY + 5,
            delta=5.0,
            detected_at=HORIZON - DAY,
        )
        store.add_clock_anomaly(
            session_id=new_sid,
            kind="forward-jump",
            wall_before=HORIZON + DAY,
            wall_after=HORIZON + DAY + 5,
            delta=5.0,
            detected_at=HORIZON + DAY,
        )

        result = store.prune(before=HORIZON)

        assert result.as_dict() == {
            "events": 1,
            "minute_levels": 3,
            "gaps": 1,
            "clock_anomalies": 1,
            "sessions": 1,
        }
        assert result.total == 7
        assert [e.start for e in store.events()] == [HORIZON + DAY]
        assert [m.minute_start for m in store.minute_levels()] == [HORIZON + DAY]
        assert [g.start for g in store.gaps()] == [HORIZON - 300]  # straddling gap kept
        assert [a.detected_at for a in store.clock_anomalies()] == [HORIZON + DAY]
        assert [s.id for s in store.sessions()] == [new_sid]
        # Calibration history is exempt by design and must survive a prune untouched.
        store.add_calibration(48.0, "test", effective_from=HORIZON - 10 * DAY)
        store.prune(before=HORIZON)
        assert len(store.calibration_history()) == 1


# --- 2. the ambient ledger is pruned by the monitor's real startup path ------------


def test_monitor_startup_prunes_the_ambient_ledger(tmp_path, monkeypatch, capsys):
    """The scenario from the issue: retention_days set, ambient ledger on, old minute
    rows in the store. Before the fix the monitor printed "pruned 1 event(s)" and the
    minute rows stayed."""
    db = tmp_path / "olive.db"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"db_path": str(db), "retention_days": 1, "ambient_ledger": True}))
    now = 1_000_000.0
    ancient = 0.5
    # Distinctive seeded timestamps: the synthetic capture's clock starts at 0 and will
    # write its own minute rows at 0.0 / 60.0, so the seeded ones sit at +0.5 offsets.
    seeded = [ancient + 60 * i for i in range(5)]
    with EventStore(db) as store:
        store.add_event(Event(ancient, ancient + 1, 1.0, -10.0, -14.0))
        for start in seeded:
            store.add_minute_level(_minute(start))
        assert len(store.minute_levels()) == 5

    def fake_live_source(sample_rate=16000, frame_size=1600, stats=None):
        yield from synthetic_session(6.0, [LoudRegion(1.0, 4.0, 0.4)], frame_size=frame_size)

    monkeypatch.setattr(capture_live, "live_source", fake_live_source)
    monitor_main(["--config", str(cfg)], now=now)
    out = capsys.readouterr().out
    assert "Retention: pruned 1 event(s), 5 ambient minute(s)," in out

    with EventStore(db) as store:
        remaining = {m.minute_start for m in store.minute_levels()}
    assert not (remaining & set(seeded)), (
        "ambient minutes older than the horizon survived the startup prune"
    )


def test_json_retention_line_carries_per_table_counts(tmp_path, monkeypatch, capsys):
    db = tmp_path / "olive.db"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"db_path": str(db), "retention_days": 1, "log_format": "json"}))
    with EventStore(db) as store:
        store.add_minute_level(_minute(0.0))
        store.add_minute_level(_minute(60.0))

    def fake_live_source(sample_rate=16000, frame_size=1600, stats=None):
        yield from synthetic_session(2.0, [], frame_size=frame_size)

    monkeypatch.setattr(capture_live, "live_source", fake_live_source)
    monitor_main(["--config", str(cfg)], now=1_000_000.0)
    lines = [json.loads(ln) for ln in capsys.readouterr().out.splitlines() if ln.startswith("{")]
    retention = [ln for ln in lines if ln["event"] == "retention_pruned"]
    assert len(retention) == 1
    assert retention[0]["pruned_by_table"] == {
        "events": 0,
        "minute_levels": 2,
        "gaps": 0,
        "clock_anomalies": 0,
        "sessions": 0,
    }
    assert retention[0]["pruned"] == 2


# --- 3. the session rule errs toward keeping -----------------------------------------


def test_crashed_session_is_kept_while_its_frame_counters_vouch_for_retained_time(tmp_path):
    """No ended_at (the run died), but the checkpointed counters prove it ran past the
    horizon. It must stay: deleting it would turn retained quiet time into "not
    monitored" (the coverage arithmetic reads the same vouched-for end)."""
    with EventStore(tmp_path / "olive.db") as store:
        sid = _session(store, HORIZON - 600)
        # 16000 Hz / 1600-sample frames = 0.1 s per frame; 12,000 frames = 1,200 s.
        store.update_session(sid, frames_seen=12_000, frames_dropped=0)
        assert store.sessions()[0].last_vouched_at == HORIZON + 600
        result = store.prune(before=HORIZON)
        assert result.sessions == 0
        assert [s.id for s in store.sessions()] == [sid]

        # The same crashed run with counters that stop before the horizon goes.
        dead = _session(store, HORIZON - 3 * DAY)
        store.update_session(dead, frames_seen=10, frames_dropped=0)
        assert store.prune(before=HORIZON).sessions == 1
        assert [s.id for s in store.sessions()] == [sid]


def test_legacy_session_with_no_framing_vouches_only_for_its_start(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        sid = store.start_session(
            started_at=HORIZON - 10,
            device_label="",
            mic_model="",
            placement_note="",
            tz="",
            calibration_offset=None,
            calibration_note=None,
            app_version="",
        )
        store.update_session(sid, frames_seen=999, frames_dropped=0)  # no rate/frame size
        assert store.sessions()[0].last_vouched_at == HORIZON - 10
        assert store.prune(before=HORIZON).sessions == 1


def test_session_still_referenced_by_a_retained_row_is_never_deleted(tmp_path):
    """Cannot happen by construction (a session that ended before the horizon cannot
    own an event that started after it), so manufacture it with raw SQL to prove the
    reference check holds independently of that invariant."""
    with EventStore(tmp_path / "olive.db") as store:
        sid = _session(store, HORIZON - 3 * DAY)
        store.update_session(sid, frames_seen=10, frames_dropped=0, ended_at=HORIZON - 2 * DAY)
        store.add_event(_ev(HORIZON + DAY), session_id=sid)
        assert store.prune(before=HORIZON).sessions == 0
        assert [s.id for s in store.sessions()] == [sid]


def test_prune_is_atomic(tmp_path, monkeypatch):
    """A failure partway through leaves the store as it was, not half-pruned."""

    class FailingConn:
        """Delegates to the real connection; fails on the third DELETE."""

        def __init__(self, real: sqlite3.Connection) -> None:
            self._real = real

        def execute(self, sql: str, *args):
            if sql.startswith("DELETE FROM gaps"):
                raise sqlite3.OperationalError("simulated failure mid-prune")
            return self._real.execute(sql, *args)

        def __getattr__(self, name: str):
            return getattr(self._real, name)

    with EventStore(tmp_path / "olive.db") as store:
        store.add_event(_ev(HORIZON - DAY))
        store.add_minute_level(_minute(HORIZON - DAY))
        real = store._conn
        monkeypatch.setattr(store, "_conn", FailingConn(real))
        try:
            store.prune(before=HORIZON)
        except sqlite3.OperationalError:
            pass
        else:  # pragma: no cover - the wrapper guarantees the raise
            raise AssertionError("expected the simulated failure to propagate")
        monkeypatch.setattr(store, "_conn", real)
        assert len(store.events()) == 1
        assert len(store.minute_levels()) == 1
