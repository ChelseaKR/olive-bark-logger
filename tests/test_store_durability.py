"""SQLite durability, migrations, sessions (lineage), and retention pruning."""

from __future__ import annotations

import sqlite3

from monitor.detector import Event
from store import EventStore
from store.db import _MIGRATIONS, SCHEMA_VERSION


def _ev(start: float) -> Event:
    return Event(start=start, end=start + 1, duration=1.0, peak_level=-10.0, avg_level=-14.0)


def test_wal_mode_enabled(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"


def test_fresh_db_is_at_latest_schema_version(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        v = store._conn.execute("PRAGMA user_version").fetchone()[0]
        assert v == SCHEMA_VERSION
        assert store.integrity_ok()


def test_old_v1_database_upgrades_in_place(tmp_path):
    db = tmp_path / "olive.db"
    # Hand-build a v1 database (events + calibration only, user_version=1).
    conn = sqlite3.connect(db)
    conn.executescript(_MIGRATIONS[0])
    conn.execute("PRAGMA user_version = 1")
    conn.execute(
        "INSERT INTO events (start, end, duration, peak_level, avg_level) VALUES (1,2,1,-9,-12)"
    )
    conn.commit()
    conn.close()

    # Opening it should migrate to the latest schema and keep the old row.
    with EventStore(db) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert len(store.events()) == 1
        assert store.latest_session() is None  # no sessions yet, but the table exists
        store._conn.execute("SELECT session_id FROM events")  # column now present


def test_crash_recovery_second_connection_reads_committed_events(tmp_path):
    db = tmp_path / "olive.db"
    store1 = EventStore(db)
    for t in (10.0, 20.0, 30.0):
        store1.add_event(_ev(t))
    # Simulate an ungraceful exit: open a *second* connection without closing the first.
    store2 = EventStore(db)
    assert len(store2.events()) == 3
    assert store2.integrity_ok()
    store1.close()
    store2.close()


def test_prune_removes_old_events(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        for t in (100.0, 200.0, 300.0, 400.0):
            store.add_event(_ev(t))
        removed = store.prune(before=250.0)
        assert removed == 2
        remaining = [e.start for e in store.events()]
        assert remaining == [300.0, 400.0]


def test_session_lifecycle(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        sid = store.start_session(
            started_at=1000.0,
            device_label="pi-1",
            mic_model="USB mic",
            placement_note="by the wall",
            tz="America/Los_Angeles",
            calibration_offset=3.0,
            calibration_note="bench",
            app_version="0.1.0",
        )
        store.add_event(_ev(1001.0), session_id=sid)
        store.update_session(sid, frames_seen=950, frames_dropped=50, ended_at=2000.0)

        s = store.latest_session()
        assert s is not None
        assert s.id == sid
        assert s.device_label == "pi-1"
        assert s.ended_at == 2000.0
        assert s.frames_seen == 950
        assert s.frame_coverage == 0.95


def test_latest_session_none_when_empty(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        assert store.latest_session() is None
