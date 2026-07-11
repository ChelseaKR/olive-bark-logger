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


def test_old_v2_database_upgrades_and_gains_clock_anomalies(tmp_path):
    db = tmp_path / "olive.db"
    # Hand-build a v2 database (events + calibration + sessions, user_version=2).
    conn = sqlite3.connect(db)
    conn.executescript(_MIGRATIONS[0])
    conn.executescript(_MIGRATIONS[1])
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()

    with EventStore(db) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        # The new table exists and is queryable, empty to start.
        assert store.clock_anomalies() == []
        store.add_clock_anomaly(
            session_id=None,
            kind="forward-jump",
            wall_before=1000.0,
            wall_after=8200.0,
            delta=7200.0,
            detected_at=8200.0,
        )
        assert len(store.clock_anomalies()) == 1
        assert store.integrity_ok()


def test_migrations_record_applied_timestamps(tmp_path):
    """`schema_migrations` records when each migration ran. The v3 timestamp is the
    forensic era boundary between rows that may carry a baked-in calibration offset
    (pre-v3 binaries) and raw-level rows (ADR-0003)."""
    import time

    # Fresh DB: every migration ran now, so every version has a timestamp.
    before = time.time()
    with EventStore(tmp_path / "fresh.db") as store:
        for v in range(1, SCHEMA_VERSION + 1):
            at = store.migration_applied_at(v)
            assert at is not None
            assert before <= at <= time.time()
        assert store.migration_applied_at(99) is None  # never applied

    # A v2-era DB upgraded in place: v1/v2 predate the bookkeeping (honestly unknown),
    # v3 records the upgrade moment — the baked-era/raw-era boundary for this database.
    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy)
    conn.executescript(_MIGRATIONS[0])
    conn.executescript(_MIGRATIONS[1])
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()
    upgrade_start = time.time()
    with EventStore(legacy) as store:
        assert store.migration_applied_at(1) is None
        assert store.migration_applied_at(2) is None
        at3 = store.migration_applied_at(3)
        assert at3 is not None
        assert upgrade_start <= at3 <= time.time()


def test_old_v2_database_upgrades_to_v3_preserving_offset_as_epoch_zero(tmp_path):
    db = tmp_path / "olive.db"
    # Hand-build a v2 database (events + calibration + sessions) with a single legacy
    # calibration row, user_version=2.
    conn = sqlite3.connect(db)
    conn.executescript(_MIGRATIONS[0])
    conn.executescript(_MIGRATIONS[1])
    conn.execute("PRAGMA user_version = 2")
    conn.execute("INSERT INTO calibration (id, offset, note) VALUES (1, 7.5, 'bench cal')")
    conn.commit()
    conn.close()

    # Opening it migrates to v3 and preserves the old offset as the first epoch (from 0).
    with EventStore(db) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        history = store.calibration_history()
        assert len(history) == 1
        epoch = history[0]
        assert epoch.effective_from == 0.0
        assert epoch.offset == 7.5
        assert epoch.note == "bench cal"
        assert epoch.reference_instrument is None
        # Backward-compat accessor still returns the latest (offset, note).
        assert store.get_calibration() == (7.5, "bench cal")
        # The offset is in force for any timestamp at/after the record start.
        assert store.calibration_at(0.0) == 7.5
        assert store.calibration_at(10_000.0) == 7.5


def test_add_calibration_is_append_only_and_time_addressable(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        assert store.calibration_history() == []
        assert store.calibration_at(100.0) is None  # empty -> caller falls back to config

        store.add_calibration(3.0, "first", effective_from=100.0)
        store.add_calibration(9.0, "second", reference_instrument="B&K 2250", effective_from=500.0)

        history = store.calibration_history()
        assert [e.offset for e in history] == [3.0, 9.0]  # append-only, oldest first
        assert history[1].reference_instrument == "B&K 2250"
        # get_calibration returns the latest epoch for backward compat.
        assert store.get_calibration() == (9.0, "second")
        # calibration_at resolves the epoch in force at each instant.
        assert store.calibration_at(50.0) == 3.0  # before first epoch -> earliest offset
        assert store.calibration_at(100.0) == 3.0
        assert store.calibration_at(300.0) == 3.0
        assert store.calibration_at(500.0) == 9.0
        assert store.calibration_at(9_999.0) == 9.0


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


def test_v2_database_upgrades_and_legacy_session_params_are_none(tmp_path):
    db = tmp_path / "olive.db"
    # Hand-build a v2 database (events + calibration + sessions, no detection-param
    # columns) with one legacy session row, then open it through EventStore.
    conn = sqlite3.connect(db)
    conn.executescript(_MIGRATIONS[0])
    conn.executescript(_MIGRATIONS[1])
    conn.execute("PRAGMA user_version = 2")
    conn.execute(
        "INSERT INTO sessions (started_at, device_label, mic_model, placement_note, tz, "
        "calibration_offset, calibration_note, app_version) "
        "VALUES (500, 'pi-legacy', 'mic', 'wall', 'UTC', 0.0, 'note', '0.0.1')"
    )
    conn.commit()
    conn.close()

    with EventStore(db) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        # The five new columns exist and the legacy row reads them back as None.
        cols = {r[1] for r in store._conn.execute("PRAGMA table_info(sessions)")}
        assert {
            "threshold_dbfs",
            "min_duration_s",
            "debounce_s",
            "sample_rate",
            "frame_size",
        } <= cols
        s = store.latest_session()
        assert s is not None
        assert s.device_label == "pi-legacy"
        assert s.threshold_dbfs is None
        assert s.min_duration_s is None
        assert s.debounce_s is None
        assert s.sample_rate is None
        assert s.frame_size is None


def test_start_session_round_trips_detection_params(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        sid = store.start_session(
            started_at=1000.0,
            device_label="pi-1",
            mic_model="USB mic",
            placement_note="by the wall",
            tz="UTC",
            calibration_offset=0.0,
            calibration_note="bench",
            app_version="0.1.0",
            threshold_dbfs=-42.0,
            min_duration_s=0.5,
            debounce_s=1.5,
            sample_rate=22050,
            frame_size=2205,
        )
        s = store.latest_session()
        assert s is not None
        assert s.id == sid
        assert s.threshold_dbfs == -42.0
        assert s.min_duration_s == 0.5
        assert s.debounce_s == 1.5
        assert s.sample_rate == 22050
        assert s.frame_size == 2205


def test_sessions_returns_all_ordered_oldest_first(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        common = dict(
            device_label="pi-1",
            mic_model="mic",
            placement_note="wall",
            tz="UTC",
            calibration_offset=0.0,
            calibration_note="note",
            app_version="0.1.0",
        )
        store.start_session(started_at=3000.0, threshold_dbfs=-30.0, **common)
        store.start_session(started_at=1000.0, threshold_dbfs=-40.0, **common)
        store.start_session(started_at=2000.0, threshold_dbfs=-35.0, **common)
        starts = [s.started_at for s in store.sessions()]
        assert starts == [1000.0, 2000.0, 3000.0]
