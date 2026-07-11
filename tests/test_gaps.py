"""Monitoring-gap ledger: schema, add_gap/gaps roundtrip, CHECK constraint, migration."""

from __future__ import annotations

import sqlite3

import pytest
from store import EventStore, Gap
from store.db import _MIGRATIONS, SCHEMA_VERSION


def test_add_gap_and_query_roundtrip(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        gid = store.add_gap(100.0, 250.0, "device-error", session_id=7)
        assert gid > 0
        gaps = store.gaps()
        assert len(gaps) == 1
        g = gaps[0]
        assert isinstance(g, Gap)
        assert (g.start, g.end, g.reason, g.session_id) == (100.0, 250.0, "device-error", 7)
        assert g.duration == 150.0


def test_gaps_window_uses_overlap(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        store.add_gap(0.0, 100.0, "shutdown")
        store.add_gap(200.0, 300.0, "device-error")
        store.add_gap(500.0, 600.0, "clock-jump")
        # Window [150, 550) overlaps the middle gap fully and the last gap partially.
        got = store.gaps(since=150.0, until=550.0)
        assert [(g.start, g.end) for g in got] == [(200.0, 300.0), (500.0, 600.0)]
        # Ordering is by start ascending.
        assert store.gaps()[0].start == 0.0


def test_reason_check_constraint_rejects_unknown(tmp_path):
    with EventStore(tmp_path / "olive.db") as store, pytest.raises(sqlite3.IntegrityError):
        store.add_gap(0.0, 1.0, "meteor-strike")


def test_all_valid_reasons_accepted(tmp_path):
    with EventStore(tmp_path / "olive.db") as store:
        for reason in ("device-error", "shutdown", "clock-jump"):
            store.add_gap(0.0, 1.0, reason)
        assert {g.reason for g in store.gaps()} == {"device-error", "shutdown", "clock-jump"}


def test_migration_adds_gaps_table_to_v2_database(tmp_path):
    db = tmp_path / "olive.db"
    # Hand-build a pre-gaps (v2) database: run migrations 0 and 1 only.
    conn = sqlite3.connect(db)
    conn.executescript(_MIGRATIONS[0])
    conn.executescript(_MIGRATIONS[1])
    conn.execute("PRAGMA user_version = 2")
    conn.execute(
        "INSERT INTO events (start, end, duration, peak_level, avg_level) VALUES (1,2,1,-9,-12)"
    )
    conn.commit()
    conn.close()

    # Opening it migrates in place: the gaps table appears and old data survives.
    with EventStore(db) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert len(store.events()) == 1
        assert store.gaps() == []  # table exists and is empty
        store.add_gap(10.0, 20.0, "shutdown")
        assert len(store.gaps()) == 1
        assert store.integrity_ok()
