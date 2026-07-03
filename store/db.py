"""SQLite persistence for events, calibration, and capture sessions.

The schema is the privacy guarantee made concrete: there is no column anywhere that
could hold audio. An event row is six numbers and an optional short tag string; a
session row is metadata about *where and how* a run measured (for data lineage and the
bias audit) plus frame-coverage counters. The calibration row records the offset and a
human note. That is the entire data model.

Durability: WAL journaling with synchronous=NORMAL survives process and OS crashes
without corruption. Schema changes are applied as ordered migrations keyed on
PRAGMA user_version, so an existing database upgrades in place.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from monitor.detector import Event

SCHEMA_VERSION = 3

# Ordered migrations. Each entry upgrades the database from version i to i+1. A fresh
# database (user_version 0) runs them all; an existing one runs only the new ones.
_MIGRATIONS: list[str] = [
    # 0 -> 1: events + calibration
    """
    CREATE TABLE events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        start       REAL NOT NULL,   -- unix seconds
        end         REAL NOT NULL,   -- unix seconds
        duration    REAL NOT NULL,   -- seconds
        peak_level  REAL NOT NULL,   -- dBFS
        avg_level   REAL NOT NULL,   -- dBFS
        coarse_tag  TEXT             -- optional bark-like/ambient hint; never audio
    );
    CREATE INDEX idx_events_start ON events(start);
    CREATE TABLE calibration (
        id      INTEGER PRIMARY KEY CHECK (id = 1),  -- single row
        offset  REAL NOT NULL,
        note    TEXT NOT NULL
    );
    """,
    # 1 -> 2: capture sessions (lineage + frame coverage) and an event -> session link
    """
    CREATE TABLE sessions (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at         REAL NOT NULL,
        ended_at           REAL,
        device_label       TEXT,
        mic_model          TEXT,
        placement_note     TEXT,
        tz                 TEXT,
        calibration_offset REAL,
        calibration_note   TEXT,
        frames_seen        INTEGER NOT NULL DEFAULT 0,
        frames_dropped     INTEGER NOT NULL DEFAULT 0,
        app_version        TEXT
    );
    ALTER TABLE events ADD COLUMN session_id INTEGER;
    """,
    # 2 -> 3: detection-parameter provenance per session. Recording the detection knobs
    # and audio framing in force for a run lets a report describe each event under the
    # parameters that were active when it was logged, even after the config later changes.
    """
    ALTER TABLE sessions ADD COLUMN threshold_dbfs REAL;
    ALTER TABLE sessions ADD COLUMN min_duration_s REAL;
    ALTER TABLE sessions ADD COLUMN debounce_s REAL;
    ALTER TABLE sessions ADD COLUMN sample_rate INTEGER;
    ALTER TABLE sessions ADD COLUMN frame_size INTEGER;
    """,
]


@dataclass(frozen=True)
class Session:
    """Lineage record for one capture run. Metadata only — never any audio."""

    id: int
    started_at: float
    ended_at: float | None
    device_label: str
    mic_model: str
    placement_note: str
    tz: str
    calibration_offset: float | None
    calibration_note: str | None
    frames_seen: int
    frames_dropped: int
    app_version: str
    # Detection parameters in force during this run. Optional because sessions written
    # before schema v3 (legacy rows) have no record of them and read back as None.
    threshold_dbfs: float | None = None
    min_duration_s: float | None = None
    debounce_s: float | None = None
    sample_rate: int | None = None
    frame_size: int | None = None

    @property
    def frame_coverage(self) -> float:
        """Fraction of frames processed vs offered (1.0 if nothing was dropped)."""
        total = self.frames_seen + self.frames_dropped
        return 1.0 if total == 0 else self.frames_seen / total


class EventStore:
    """Event log, calibration record, and capture-session lineage."""

    def __init__(self, path: str | Path = "olive.db") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        # Durability + integrity pragmas. WAL lets a reader (e.g. the report) run while
        # the monitor writes; synchronous=NORMAL is crash-safe under WAL.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        for target in range(version, len(_MIGRATIONS)):
            self._conn.executescript(_MIGRATIONS[target])
            self._conn.execute(f"PRAGMA user_version = {target + 1}")
        self._conn.commit()

    # -- events --------------------------------------------------------------
    def add_event(self, event: Event, *, session_id: int | None = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO events (start, end, duration, peak_level, avg_level, coarse_tag, "
            "session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.start,
                event.end,
                event.duration,
                event.peak_level,
                event.avg_level,
                event.coarse_tag,
                session_id,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def events(self, *, since: float | None = None, until: float | None = None) -> list[Event]:
        """All events, optionally bounded by [since, until) on start time, ordered."""
        sql = "SELECT start, end, duration, peak_level, avg_level, coarse_tag FROM events"
        clauses: list[str] = []
        params: list[float] = []
        if since is not None:
            clauses.append("start >= ?")
            params.append(since)
        if until is not None:
            clauses.append("start < ?")
            params.append(until)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY start ASC"
        rows: Iterable[sqlite3.Row] = self._conn.execute(sql, params)
        return [
            Event(
                start=r["start"],
                end=r["end"],
                duration=r["duration"],
                peak_level=r["peak_level"],
                avg_level=r["avg_level"],
                coarse_tag=r["coarse_tag"],
            )
            for r in rows
        ]

    def prune(self, *, before: float) -> int:
        """Delete events that started before `before` (unix seconds). Returns the count."""
        cur = self._conn.execute("DELETE FROM events WHERE start < ?", (before,))
        self._conn.commit()
        return cur.rowcount

    # -- calibration ---------------------------------------------------------
    def set_calibration(self, offset: float, note: str) -> None:
        self._conn.execute(
            "INSERT INTO calibration (id, offset, note) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET offset = excluded.offset, note = excluded.note",
            (offset, note),
        )
        self._conn.commit()

    def get_calibration(self) -> tuple[float, str] | None:
        row = self._conn.execute("SELECT offset, note FROM calibration WHERE id = 1").fetchone()
        return (row["offset"], row["note"]) if row else None

    # -- sessions (lineage) --------------------------------------------------
    def start_session(
        self,
        *,
        started_at: float,
        device_label: str,
        mic_model: str,
        placement_note: str,
        tz: str,
        calibration_offset: float,
        calibration_note: str,
        app_version: str,
        threshold_dbfs: float | None = None,
        min_duration_s: float | None = None,
        debounce_s: float | None = None,
        sample_rate: int | None = None,
        frame_size: int | None = None,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (started_at, device_label, mic_model, placement_note, tz, "
            "calibration_offset, calibration_note, app_version, threshold_dbfs, min_duration_s, "
            "debounce_s, sample_rate, frame_size) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                started_at,
                device_label,
                mic_model,
                placement_note,
                tz,
                calibration_offset,
                calibration_note,
                app_version,
                threshold_dbfs,
                min_duration_s,
                debounce_s,
                sample_rate,
                frame_size,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def update_session(
        self,
        session_id: int,
        *,
        frames_seen: int,
        frames_dropped: int,
        ended_at: float | None = None,
    ) -> None:
        self._conn.execute(
            "UPDATE sessions SET frames_seen = ?, frames_dropped = ?, ended_at = ? WHERE id = ?",
            (frames_seen, frames_dropped, ended_at, session_id),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            device_label=row["device_label"] or "",
            mic_model=row["mic_model"] or "",
            placement_note=row["placement_note"] or "",
            tz=row["tz"] or "",
            calibration_offset=row["calibration_offset"],
            calibration_note=row["calibration_note"],
            frames_seen=row["frames_seen"],
            frames_dropped=row["frames_dropped"],
            app_version=row["app_version"] or "",
            threshold_dbfs=row["threshold_dbfs"],
            min_duration_s=row["min_duration_s"],
            debounce_s=row["debounce_s"],
            sample_rate=row["sample_rate"],
            frame_size=row["frame_size"],
        )

    def latest_session(self) -> Session | None:
        row = self._conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC, id DESC LIMIT 1"
        ).fetchone()
        return None if row is None else self._row_to_session(row)

    def sessions(self) -> list[Session]:
        """All capture sessions, oldest first — the ordered parameter epochs a report
        uses to describe each event under the settings in force when it was logged."""
        rows = self._conn.execute("SELECT * FROM sessions ORDER BY started_at ASC, id ASC")
        return [self._row_to_session(r) for r in rows]

    # -- integrity -----------------------------------------------------------
    def integrity_ok(self) -> bool:
        """True if SQLite's own integrity check passes (used by crash-recovery tests)."""
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row) and row[0] == "ok"

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> EventStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
