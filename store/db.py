"""SQLite persistence for events, calibration, and capture sessions.

The schema is the privacy guarantee made concrete: there is no column anywhere that
could hold audio. An event row is six numbers and an optional short tag string; a
session row is metadata about *where and how* a run measured (for data lineage and the
bias audit) plus frame-coverage counters. Calibration is an append-only history of
(effective_from, offset, note, reference_instrument) rows — the offset in force at any
instant is the latest row whose effective_from is at or before it, and offsets are
applied at *render* time so persisted event levels stay raw. That is the entire data
model.

Durability: WAL journaling with synchronous=NORMAL survives process and OS crashes
without corruption. Schema changes are applied as ordered migrations keyed on
PRAGMA user_version, so an existing database upgrades in place.
"""

from __future__ import annotations

import sqlite3
import time
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
    # 2 -> 3: calibration becomes an append-only history keyed by effective_from.
    # Offsets are no longer baked into stored levels; they are applied at render time.
    # The single legacy `calibration` row (if any) is preserved as the first history
    # epoch with effective_from=0 so every previously stored event keeps its offset.
    """
    CREATE TABLE calibration_history (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        effective_from       REAL NOT NULL,   -- unix seconds; offset applies from here on
        offset               REAL NOT NULL,   -- dB added to raw dBFS to approximate SPL
        note                 TEXT,
        reference_instrument TEXT             -- provenance of the reference meter, if any
    );
    CREATE INDEX idx_calibration_effective ON calibration_history(effective_from);
    INSERT INTO calibration_history (effective_from, offset, note)
        SELECT 0, offset, note FROM calibration WHERE id = 1;
    """,
]


@dataclass(frozen=True)
class CalibrationEpoch:
    """One entry in the append-only calibration history. Metadata only — never audio."""

    id: int
    effective_from: float  # unix seconds; this offset is in force from here forward
    offset: float  # dB added to raw dBFS to approximate SPL
    note: str | None
    reference_instrument: str | None


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
    def add_calibration(
        self,
        offset: float,
        note: str,
        *,
        reference_instrument: str | None = None,
        effective_from: float | None = None,
    ) -> int:
        """Append a new calibration epoch. Never updates an existing row.

        Calibration is an append-only ledger so the meaning of a historical event never
        changes: `olive-calibrate` is the only writer. `effective_from` defaults to now,
        so the new offset applies to events measured from this point forward; passing an
        explicit value (e.g. 0 for a bootstrap epoch) is supported for tests and imports.
        """
        when = time.time() if effective_from is None else effective_from
        cur = self._conn.execute(
            "INSERT INTO calibration_history (effective_from, offset, note, "
            "reference_instrument) VALUES (?, ?, ?, ?)",
            (when, offset, note, reference_instrument),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def get_calibration(self) -> tuple[float, str] | None:
        """The latest calibration (offset, note) for backward compatibility, or None."""
        row = self._conn.execute(
            "SELECT offset, note FROM calibration_history "
            "ORDER BY effective_from DESC, id DESC LIMIT 1"
        ).fetchone()
        return (row["offset"], row["note"]) if row else None

    def calibration_history(self) -> list[CalibrationEpoch]:
        """All calibration epochs, oldest first (by effective_from, then insertion)."""
        rows = self._conn.execute(
            "SELECT id, effective_from, offset, note, reference_instrument "
            "FROM calibration_history ORDER BY effective_from ASC, id ASC"
        )
        return [
            CalibrationEpoch(
                id=r["id"],
                effective_from=r["effective_from"],
                offset=r["offset"],
                note=r["note"],
                reference_instrument=r["reference_instrument"],
            )
            for r in rows
        ]

    def calibration_at(self, ts: float) -> float | None:
        """The offset in force at time `ts`: the latest epoch effective at or before it.

        Returns None only when no calibration has ever been recorded (empty history), so
        a caller can fall back to a bootstrap default. A timestamp earlier than the first
        epoch resolves to that first epoch's offset (epoch 0 covers all historical rows).
        """
        row = self._conn.execute(
            "SELECT offset FROM calibration_history WHERE effective_from <= ? "
            "ORDER BY effective_from DESC, id DESC LIMIT 1",
            (ts,),
        ).fetchone()
        if row is not None:
            return float(row["offset"])
        earliest = self._conn.execute(
            "SELECT offset FROM calibration_history ORDER BY effective_from ASC, id ASC LIMIT 1"
        ).fetchone()
        return float(earliest["offset"]) if earliest is not None else None

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
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (started_at, device_label, mic_model, placement_note, tz, "
            "calibration_offset, calibration_note, app_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                started_at,
                device_label,
                mic_model,
                placement_note,
                tz,
                calibration_offset,
                calibration_note,
                app_version,
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

    def latest_session(self) -> Session | None:
        row = self._conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
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
        )

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
