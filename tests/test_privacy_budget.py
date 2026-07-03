"""Merge-blocking ceiling for persisted derived sound metadata (FIX-13)."""

from __future__ import annotations

import sqlite3

from store import EventStore

EXPECTED_TABLES = {
    "events",
    "calibration",
    "sessions",
    "calibration_history",
    "schema_migrations",
    "gaps",
    "clock_anomalies",
}

EVENT_COLUMNS = {
    "id",
    "start",
    "end",
    "duration",
    "peak_level",
    "avg_level",
    "coarse_tag",
    "session_id",
    "rise_time_s",
    "loud6_s",
    "longest_run_s",
}

SIGNAL_DERIVED_FIELDS = {
    "peak_level",
    "avg_level",
    "rise_time_s",
    "loud6_s",
    "longest_run_s",
}
MAX_SIGNAL_SCALARS_PER_EVENT = 5


def _schema(db_path) -> dict[str, set[str]]:
    with EventStore(db_path):
        pass
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        return {
            table: {
                row[1].lower()
                for row in conn.execute("SELECT * FROM pragma_table_info(?)", (table,))
            }
            for table in tables
        }
    finally:
        conn.close()


def test_persisted_tables_and_event_shape_match_budget(tmp_path):
    schema = _schema(tmp_path / "olive.db")
    assert set(schema) == EXPECTED_TABLES, "persisted table set changed; review the privacy budget"
    assert schema["events"] == EVENT_COLUMNS, "event schema changed; review the privacy budget"
    assert schema["events"] >= SIGNAL_DERIVED_FIELDS
    assert len(SIGNAL_DERIVED_FIELDS) <= MAX_SIGNAL_SCALARS_PER_EVENT


def test_schema_has_no_spectral_or_reconstruction_fields(tmp_path):
    schema = _schema(tmp_path / "olive.db")
    forbidden = ("spectrum", "spectral", "frequency", "fft", "embedding", "fingerprint")
    offenders = {
        f"{table}.{column}"
        for table, columns in schema.items()
        for column in columns
        if any(word in column for word in forbidden)
    }
    assert not offenders, f"fields exceed the derived-data privacy budget: {offenders}"
