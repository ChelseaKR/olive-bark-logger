"""Ambient baseline ledger (EXP-01): schema, add_minute_level/minute_levels roundtrip,
migration. Mirrors tests/test_gaps.py's structure for the analogous FIX-03 table."""

from __future__ import annotations

import sqlite3

from monitor.ambient import MinuteLevel
from store import EventStore
from store.db import _MIGRATIONS, SCHEMA_VERSION


def _minute(minute_start: float = 0.0) -> MinuteLevel:
    return MinuteLevel(
        minute_start=minute_start,
        min_dbfs=-40.0,
        median_dbfs=-35.0,
        max_dbfs=-30.0,
        l90_dbfs=-38.0,
        frame_count=600,
    )


def test_add_minute_level_and_query_roundtrip(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        mid = store.add_minute_level(_minute(120.0), session_id=3)
        assert mid > 0
        rows = store.minute_levels()
        assert len(rows) == 1
        m = rows[0]
        assert isinstance(m, MinuteLevel)
        assert m.minute_start == 120.0
        assert (m.min_dbfs, m.median_dbfs, m.max_dbfs, m.l90_dbfs) == (-40.0, -35.0, -30.0, -38.0)
        assert m.frame_count == 600


def test_minute_levels_window_is_half_open_on_start(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        store.add_minute_level(_minute(0.0))
        store.add_minute_level(_minute(60.0))
        store.add_minute_level(_minute(120.0))
        got = store.minute_levels(since=60.0, until=120.0)
        assert [m.minute_start for m in got] == [60.0]
        assert [m.minute_start for m in store.minute_levels()] == [0.0, 60.0, 120.0]


def test_minute_levels_ordered_by_minute_start(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        store.add_minute_level(_minute(180.0))
        store.add_minute_level(_minute(0.0))
        store.add_minute_level(_minute(60.0))
        assert [m.minute_start for m in store.minute_levels()] == [0.0, 60.0, 180.0]


def test_no_minute_levels_by_default(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        assert store.minute_levels() == []


def test_migration_adds_minute_levels_table_to_v7_database(tmp_path):
    db = tmp_path / "olive.db"
    # Hand-build a pre-ambient-ledger (v7) database: run migrations 0..6 only.
    conn = sqlite3.connect(db)
    for migration in _MIGRATIONS[:7]:
        conn.executescript(migration)
    conn.execute("PRAGMA user_version = 7")
    conn.execute(
        "INSERT INTO events (start, end, duration, peak_level, avg_level) VALUES (1,2,1,-9,-12)"
    )
    conn.commit()
    conn.close()

    # Opening it migrates in place: the minute_levels table appears and old data survives.
    with EventStore(db) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert len(store.events()) == 1
        assert store.minute_levels() == []  # table exists and is empty
        store.add_minute_level(_minute(0.0))
        assert len(store.minute_levels()) == 1
        assert store.integrity_ok()
