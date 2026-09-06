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
    "minute_levels",
    "drift_advisories",
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

# Ambient baseline ledger (EXP-01, opt-in, off by default). One row per wall-clock
# minute while enabled; see docs/audits/derived-data-budget.md for the analysis.
MINUTE_LEVEL_COLUMNS = {
    "id",
    "session_id",
    "minute_start",
    "min_dbfs",
    "median_dbfs",
    "max_dbfs",
    "l90_dbfs",
    "frame_count",
}
SIGNAL_DERIVED_MINUTE_FIELDS = {
    "min_dbfs",
    "median_dbfs",
    "max_dbfs",
    "l90_dbfs",
}
MAX_SIGNAL_SCALARS_PER_MINUTE = 4

# Advisory drift watch (EXP-04). Rows are written only when a comparison trips, and they
# hold *differences between two aggregates of the minute ledger* rather than any new
# reading: two dB deltas, a tolerance, two minute counts and four window bounds. No new
# signal-derived quantity enters the store here, which is why this table adds nothing to
# the per-minute ceiling above. See docs/audits/derived-data-budget.md.
DRIFT_ADVISORY_COLUMNS = {
    "id",
    "session_id",
    "detected_at",
    "calibration_epoch",
    "reference_start",
    "reference_end",
    "recent_start",
    "recent_end",
    "reference_minutes",
    "recent_minutes",
    "median_delta_db",
    "l90_delta_db",
    "tolerance_db",
}
# Every signal-derived number in a drift row is a difference of two `minute_levels`
# statistics that are already inside the budget above. Nothing here is a fresh
# measurement of the room.
SIGNAL_DERIVED_DRIFT_FIELDS = {"median_delta_db", "l90_delta_db"}


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


def test_minute_levels_shape_matches_budget(tmp_path):
    """The opt-in ambient ledger (EXP-01) stays inside its own, separately declared
    per-minute ceiling — see docs/audits/derived-data-budget.md."""
    schema = _schema(tmp_path / "olive.db")
    assert schema["minute_levels"] == MINUTE_LEVEL_COLUMNS, (
        "minute_levels schema changed; review the privacy budget"
    )
    assert schema["minute_levels"] >= SIGNAL_DERIVED_MINUTE_FIELDS
    assert len(SIGNAL_DERIVED_MINUTE_FIELDS) <= MAX_SIGNAL_SCALARS_PER_MINUTE


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


def test_drift_advisory_shape_matches_budget(tmp_path):
    """EXP-04 stores differences of already-budgeted aggregates, and nothing else.

    The check that matters is not the column count but what the columns *are*: a drift
    row must never smuggle in a new per-minute or per-frame quantity under the cover of
    an advisory.
    """
    schema = _schema(tmp_path / "olive.db")
    assert schema["drift_advisories"] == DRIFT_ADVISORY_COLUMNS, (
        "drift_advisories schema changed; review the privacy budget"
    )
    assert schema["drift_advisories"] >= SIGNAL_DERIVED_DRIFT_FIELDS
    # Each signal-derived drift field is a delta of a field already declared above.
    for field in SIGNAL_DERIVED_DRIFT_FIELDS:
        base = field.removesuffix("_delta_db") + "_dbfs"
        assert base in SIGNAL_DERIVED_MINUTE_FIELDS, (
            f"{field} is not a difference of an already-budgeted minute statistic"
        )
