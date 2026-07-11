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
PRAGMA user_version, so an existing database upgrades in place. A `schema_migrations`
side table records *when* each migration ran: those timestamps are forensic era
boundaries — in particular, the v3 timestamp separates rows whose levels may carry a
baked-in calibration offset (written by pre-v3 binaries) from rows stored raw
(see docs/adr/0003).
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from monitor.detector import Event

SCHEMA_VERSION = 6

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
    # 3 -> 4: detection-parameter provenance per session (FIX-02). Recording the
    # detection knobs and audio framing in force for a run lets a report describe each
    # event under the parameters that were active when it was logged, even after the
    # config later changes. (Originally drafted as 2 -> 3; renumbered to follow the
    # calibration-history migration that landed first.)
    """
    ALTER TABLE sessions ADD COLUMN threshold_dbfs REAL;
    ALTER TABLE sessions ADD COLUMN min_duration_s REAL;
    ALTER TABLE sessions ADD COLUMN debounce_s REAL;
    ALTER TABLE sessions ADD COLUMN sample_rate INTEGER;
    ALTER TABLE sessions ADD COLUMN frame_size INTEGER;
    """,
    # 4 -> 5: monitoring-gap ledger (FIX-03). Each row is an interval when the device
    # was *not* listening, so "no data" can be reported distinctly from a genuinely
    # quiet hour. Metadata only (two timestamps and a reason) — never any audio.
    # (Originally drafted as 2 -> 3; renumbered after the calibration-history and
    # parameter-provenance migrations landed first.)
    """
    CREATE TABLE IF NOT EXISTS gaps (
        id          INTEGER PRIMARY KEY,
        session_id  INTEGER,
        start       REAL NOT NULL,
        end         REAL NOT NULL,
        reason      TEXT NOT NULL
                    CHECK(reason IN ('device-error','shutdown','clock-jump'))
    );
    CREATE INDEX IF NOT EXISTS idx_gaps_start ON gaps(start);
    """,
    # 5 -> 6: clock-integrity anomalies (FIX-10). On RTC-less hosts (e.g. a Raspberry
    # Pi) the wall clock can jump when NTP finally syncs or after suspend/resume. We
    # track wall vs monotonic time during capture and persist any divergence here so the
    # report can disclose it. Metadata only (five numbers + a kind string) — never
    # audio. (Originally drafted as 2 -> 3; renumbered after the calibration-history,
    # parameter-provenance, and gap-ledger migrations landed first.)
    """
    CREATE TABLE clock_anomalies (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id   INTEGER,
        kind         TEXT NOT NULL,   -- 'forward-jump' or 'backward-jump'
        wall_before  REAL NOT NULL,   -- wall time expected from monotonic progression
        wall_after   REAL NOT NULL,   -- wall time actually observed
        delta        REAL NOT NULL,   -- wall_after - wall_before (signed drift, seconds)
        detected_at  REAL NOT NULL    -- wall time the divergence was noticed
    );
    CREATE INDEX idx_clock_anomalies_detected ON clock_anomalies(detected_at);
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


@dataclass(frozen=True)
class ClockAnomaly:
    """A detected wall-clock vs monotonic-clock divergence during capture. Numbers only."""

    id: int
    session_id: int | None
    kind: str
    wall_before: float
    wall_after: float
    delta: float
    detected_at: float


@dataclass(frozen=True)
class Gap:
    """One interval when the device was not listening. Metadata only — no audio.

    `reason` is one of 'device-error' (a source outage caught by resilient_source),
    'shutdown' (the monitor was not running), or 'clock-jump' (wall-clock discontinuity).
    """

    id: int
    session_id: int | None
    start: float
    end: float
    reason: str

    @property
    def duration(self) -> float:
        return self.end - self.start


class EventStore:
    """Event log, calibration record, session lineage, monitoring gaps, clock anomalies."""

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
        # Bookkeeping first (idempotent): record when each migration runs. A migration's
        # timestamp is an era boundary for interpreting old rows — e.g. events stored
        # before v3 ran may carry a baked-in calibration offset, while later rows are
        # raw (ADR-0003). Migrations applied by binaries that predate this table simply
        # have no row, which is itself honest ("time of application unknown").
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)"
        )
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        for target in range(version, len(_MIGRATIONS)):
            self._conn.executescript(_MIGRATIONS[target])
            self._conn.execute(f"PRAGMA user_version = {target + 1}")
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (target + 1, time.time()),
            )
        self._conn.commit()

    def migration_applied_at(self, version: int) -> float | None:
        """When schema migration `version` ran on this database (unix seconds), or None.

        None means the migration was applied by an older binary from before this
        bookkeeping existed, so the time is unknown. The v3 timestamp is the boundary
        between baked-offset-era event rows and raw-level rows (ADR-0003).
        """
        row = self._conn.execute(
            "SELECT applied_at FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        return float(row["applied_at"]) if row else None

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

    # -- monitoring gaps -----------------------------------------------------
    def add_gap(
        self, start: float, end: float, reason: str, *, session_id: int | None = None
    ) -> int:
        """Record an interval [start, end) when the device was not listening."""
        cur = self._conn.execute(
            "INSERT INTO gaps (session_id, start, end, reason) VALUES (?, ?, ?, ?)",
            (session_id, start, end, reason),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def gaps(self, *, since: float | None = None, until: float | None = None) -> list[Gap]:
        """Gaps overlapping [since, until), ordered by start.

        Overlap semantics (a gap counts if any part of it falls in the window) so a
        report window slicing through an outage still sees it.
        """
        sql = "SELECT id, session_id, start, end, reason FROM gaps"
        clauses: list[str] = []
        params: list[float] = []
        if since is not None:
            clauses.append("end > ?")
            params.append(since)
        if until is not None:
            clauses.append("start < ?")
            params.append(until)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY start ASC"
        rows: Iterable[sqlite3.Row] = self._conn.execute(sql, params)
        return [
            Gap(
                id=r["id"],
                session_id=r["session_id"],
                start=r["start"],
                end=r["end"],
                reason=r["reason"],
            )
            for r in rows
        ]

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
        """Persist the running frame counters for a session.

        ``ended_at`` is optional so periodic checkpoints can flush counters mid-run
        without marking the session ended: when it is None the existing ``ended_at``
        is left untouched (it stays NULL until the finally block sets the real end
        time). This is what makes crash-safe counters possible — a power cut during a
        silent night still leaves the last-checkpointed counts on disk.
        """
        if ended_at is None:
            self._conn.execute(
                "UPDATE sessions SET frames_seen = ?, frames_dropped = ? WHERE id = ?",
                (frames_seen, frames_dropped, session_id),
            )
        else:
            self._conn.execute(
                "UPDATE sessions SET frames_seen = ?, frames_dropped = ?, ended_at = ? "
                "WHERE id = ?",
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

    # -- clock anomalies -----------------------------------------------------
    def add_clock_anomaly(
        self,
        *,
        session_id: int | None,
        kind: str,
        wall_before: float,
        wall_after: float,
        delta: float,
        detected_at: float,
    ) -> int:
        """Persist one clock-jump anomaly. Metadata only — never audio."""
        cur = self._conn.execute(
            "INSERT INTO clock_anomalies (session_id, kind, wall_before, wall_after, delta, "
            "detected_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, kind, wall_before, wall_after, delta, detected_at),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def clock_anomalies(
        self, start: float | None = None, end: float | None = None
    ) -> list[ClockAnomaly]:
        """Anomalies whose detected_at falls in [start, end), ordered by detection time.

        Both bounds are optional so the report can ask for everything; the window form
        keeps this compatible with FIX-03's later gap-table queries.
        """
        sql = (
            "SELECT id, session_id, kind, wall_before, wall_after, delta, detected_at "
            "FROM clock_anomalies"
        )
        clauses: list[str] = []
        params: list[float] = []
        if start is not None:
            clauses.append("detected_at >= ?")
            params.append(start)
        if end is not None:
            clauses.append("detected_at < ?")
            params.append(end)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY detected_at ASC, id ASC"
        rows: Iterable[sqlite3.Row] = self._conn.execute(sql, params)
        return [
            ClockAnomaly(
                id=r["id"],
                session_id=r["session_id"],
                kind=r["kind"],
                wall_before=r["wall_before"],
                wall_after=r["wall_after"],
                delta=r["delta"],
                detected_at=r["detected_at"],
            )
            for r in rows
        ]

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
