"""Operator erasure: `EventStore.forget` and `olive-forget`.

A privacy-first tool needs a privacy verb. The thing that makes erasure safe to have at
all is that the hole it leaves is disclosed: a `gaps` row with reason `erased`, which
every reader that already understands "the device was not listening here" understands
too. The coverage figures subtract it, the calendar hatches it, the CSV's `monitored`
column reads `no` beside it, and the report names the window and the operator's reason.

Two properties in here are load-bearing rather than nice to have.

**The erasure row is written in the same transaction as the deletes.** A crash between
them would leave exactly the hole-with-nothing-disclosing-it that editing the SQLite
file by hand produces, and it would leave it looking like an ordinary quiet night.
:class:`TestTheDisclosureCannotBeSeparatedFromTheDeletes` drives that by making the
INSERT fail and asserting the rows came back.

**An erased night must never be able to read as quiet.** The strongest form of that is
not "the export says erased" but "the coverage arithmetic and the calendar treat those
hours as unmonitored", since the per-day figure is what an ordinance's threshold is read
from. :class:`TestAnErasedWindowIsNotQuiet` holds it there.

None of these tests pins an assertion to an incidental length or offset of the rendered
report. A control anchored to "the report is exactly N characters" stops firing the
moment an unrelated section is added, and reads as a pass while it does; every
assertion here searches the document for the words it cares about.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from monitor.ambient import MinuteLevel
from monitor.detector import Event
from monitor.drift import DriftAdvisory
from report.render import ERASED_HEADING, build_report, erased_window_lines
from store import ERASED_REASON, EventStore
from store.db import _MIGRATIONS, SCHEMA_VERSION
from store.forget import CONFIRMATION, TimestampError, describe, main, parse_moment

UTC = timezone.utc
HOUR = 3600.0
BASE = 1_700_000_000.0  # an arbitrary but fixed moment; nothing here depends on "now"


def _event(start: float, *, duration: float = 2.0) -> Event:
    return Event(start, start + duration, duration, -10.0, -14.0)


def _minute(start: float) -> MinuteLevel:
    return MinuteLevel(
        minute_start=start,
        min_dbfs=-60.0,
        median_dbfs=-50.0,
        max_dbfs=-40.0,
        l90_dbfs=-55.0,
        frame_count=100,
    )


def _advisory(detected_at: float) -> DriftAdvisory:
    return DriftAdvisory(
        calibration_epoch=0.0,
        reference_start=detected_at - 2 * HOUR,
        reference_end=detected_at - HOUR,
        recent_start=detected_at - HOUR,
        recent_end=detected_at,
        reference_minutes=60,
        recent_minutes=60,
        median_delta_db=4.0,
        l90_delta_db=3.0,
        tolerance_db=2.0,
    )


def _session(store: EventStore, started_at: float) -> int:
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


def _populated(path) -> EventStore:
    """A store with something in every table `forget` reaches, inside and outside.

    The window erased by these tests is [BASE + 2h, BASE + 4h). Each table gets one row
    inside it and one row outside, so an assertion that the right rows went cannot pass
    by the table having been empty, and one that deleted too much cannot pass either.
    """
    store = EventStore(path)
    session_id = _session(store, BASE)
    for offset in (1 * HOUR, 2 * HOUR + 60, 3 * HOUR, 5 * HOUR):
        store.add_event(_event(BASE + offset), session_id=session_id)
    for offset in (1 * HOUR, 2 * HOUR + 120, 5 * HOUR):
        store.add_minute_level(_minute(BASE + offset), session_id=session_id)
    store.add_clock_anomaly(
        kind="forward-jump",
        wall_before=BASE + 2 * HOUR + 300,
        wall_after=BASE + 2 * HOUR + 400,
        delta=100.0,
        detected_at=BASE + 2 * HOUR + 300,
        session_id=session_id,
    )
    store.add_clock_anomaly(
        kind="forward-jump",
        wall_before=BASE + 5 * HOUR,
        wall_after=BASE + 5 * HOUR + 100,
        delta=100.0,
        detected_at=BASE + 5 * HOUR,
        session_id=session_id,
    )
    for detected_at in (BASE + 2 * HOUR + 600, BASE + 5 * HOUR):
        store.add_drift_advisory(
            _advisory(detected_at), session_id=session_id, detected_at=detected_at
        )
    store.add_gap(BASE + 2 * HOUR + 900, BASE + 2 * HOUR + 1000, "device-error")
    store.add_gap(BASE + 5 * HOUR, BASE + 5 * HOUR + 100, "device-error")
    store.update_session(session_id, frames_seen=1, frames_dropped=0, ended_at=BASE + 6 * HOUR)
    return store


def _snapshot(store: EventStore) -> dict[str, list[tuple[object, ...]]]:
    """Every row in every table `forget` could touch, as comparable tuples."""
    out: dict[str, list[tuple[object, ...]]] = {}
    for table in ("events", "minute_levels", "clock_anomalies", "drift_advisories", "gaps"):
        rows = store._conn.execute(f"SELECT * FROM {table} ORDER BY id")  # noqa: S608 - fixed names
        out[table] = [tuple(r) for r in rows]
    return out


WINDOW = (BASE + 2 * HOUR, BASE + 4 * HOUR)


class TestWhatAnErasureRemovesAndLeaves:
    def test_it_removes_the_window_from_every_table_it_reaches(self, tmp_path) -> None:
        with _populated(tmp_path / "olive.db") as store:
            before = _snapshot(store)
            result = store.forget(start=WINDOW[0], end=WINDOW[1], reason="a guest")
            after = _snapshot(store)

        assert result.as_dict() == {
            "events": 2,
            "minute_levels": 1,
            "clock_anomalies": 1,
            "drift_advisories": 1,
            "gaps": 1,
        }
        # Every table lost exactly the rows inside the window and no others. The
        # gaps table is the exception: it lost one and gained the erasure row.
        for table in ("events", "minute_levels", "clock_anomalies", "drift_advisories"):
            assert len(after[table]) == len(before[table]) - result.as_dict()[table], table
            assert after[table], f"{table} was emptied; the window was supposed to be partial"

    def test_it_writes_exactly_one_erased_gap_carrying_the_reason(self, tmp_path) -> None:
        with _populated(tmp_path / "olive.db") as store:
            result = store.forget(start=WINDOW[0], end=WINDOW[1], reason="a guest")
            erased = [g for g in store.gaps() if g.erased]

        assert len(erased) == 1
        assert (erased[0].start, erased[0].end) == WINDOW
        assert erased[0].reason == ERASED_REASON
        assert erased[0].note == "a guest"
        assert result.gap_id == erased[0].id

    def test_an_erasure_with_no_reason_records_no_reason_rather_than_nothing(
        self, tmp_path
    ) -> None:
        with _populated(tmp_path / "olive.db") as store:
            store.forget(start=WINDOW[0], end=WINDOW[1])
            erased = [g for g in store.gaps() if g.erased]
        assert erased[0].note is None
        assert erased_window_lines(erased, UTC) == [
            f"{erased_window_lines(erased, UTC)[0].split(' — ')[0]} — erased (no reason given)"
        ]

    def test_an_event_straddling_the_boundary_goes(self, tmp_path) -> None:
        """Overlap, not containment. A straddling row carries measurement from inside."""
        with EventStore(tmp_path / "olive.db") as store:
            store.add_event(_event(WINDOW[0] - 1.0, duration=10.0))  # ends inside
            store.add_event(_event(WINDOW[1] - 1.0, duration=10.0))  # starts inside
            store.add_event(_event(WINDOW[1] + 100.0))  # wholly outside
            result = store.forget(start=WINDOW[0], end=WINDOW[1])
            assert result.events == 2
            assert len(store.events()) == 1

    def test_a_gap_straddling_the_boundary_is_kept(self, tmp_path) -> None:
        """It also says something about time outside the window, which the erasure
        row does not cover."""
        with EventStore(tmp_path / "olive.db") as store:
            store.add_gap(WINDOW[0] - 60.0, WINDOW[0] + 60.0, "device-error")
            store.forget(start=WINDOW[0], end=WINDOW[1])
            kept = [g for g in store.gaps() if not g.erased]
            assert len(kept) == 1

    def test_sessions_and_calibration_are_left_alone(self, tmp_path) -> None:
        """Documented on purpose: lineage for the retained rows, not measurement."""
        with _populated(tmp_path / "olive.db") as store:
            store.add_calibration(3.0, "meter", effective_from=BASE)
            store.forget(start=WINDOW[0], end=WINDOW[1])
            assert len(store.sessions()) == 1
            assert len(store.calibration_history()) == 1

    def test_an_empty_or_reversed_window_is_refused(self, tmp_path) -> None:
        with EventStore(tmp_path / "olive.db") as store:
            with pytest.raises(ValueError, match="empty or reversed"):
                store.forget(start=WINDOW[1], end=WINDOW[0])
            with pytest.raises(ValueError, match="empty or reversed"):
                store.forget(start=WINDOW[0], end=WINDOW[0])


class TestADryRunChangesNothing:
    def test_the_snapshot_is_identical_and_the_counts_are_the_real_ones(self, tmp_path) -> None:
        with _populated(tmp_path / "olive.db") as store:
            before = _snapshot(store)
            preview = store.forget(start=WINDOW[0], end=WINDOW[1], reason="x", dry_run=True)
            assert _snapshot(store) == before
            assert preview.gap_id is None

            real = store.forget(start=WINDOW[0], end=WINDOW[1], reason="x")

        # The dry run described the operation that actually followed, not a different
        # one: same counts, from the same predicates.
        assert preview.as_dict() == real.as_dict()
        assert preview.total == real.total


class TestTheDisclosureCannotBeSeparatedFromTheDeletes:
    def test_a_failure_writing_the_gap_rolls_the_deletes_back(self, tmp_path) -> None:
        """The sharp edge of the whole verb.

        A crash between the deletes and the disclosure leaves a hole with nothing
        disclosing it, which reads in the report exactly like a quiet night. So the
        two are one transaction.

        Driven with a real SQLite abort rather than a patched method: a trigger that
        refuses every INSERT into `gaps`. A mocked `execute` would prove the Python
        raised, not that the database rolled back, and the rollback is the property
        under test.
        """
        with _populated(tmp_path / "olive.db") as store:
            before = _snapshot(store)
            store._conn.executescript(
                "CREATE TRIGGER refuse_gap BEFORE INSERT ON gaps "
                "BEGIN SELECT RAISE(ABORT, 'the disk went away'); END;"
            )
            # The sabotage has to actually be in force, or this test passes by the
            # erasure simply succeeding.
            with pytest.raises(sqlite3.IntegrityError):
                store._conn.execute(
                    "INSERT INTO gaps (start, end, reason) VALUES (1, 2, 'device-error')"
                )
            store._conn.rollback()

            with pytest.raises(sqlite3.IntegrityError):
                store.forget(start=WINDOW[0], end=WINDOW[1], reason="a guest")

            store._conn.executescript("DROP TRIGGER refuse_gap;")
            assert _snapshot(store) == before, (
                "rows were deleted and the erasure row was not written: a hole with "
                "nothing disclosing it, which is the outcome this verb exists to prevent"
            )
            assert not [g for g in store.gaps() if g.erased]


class TestAnErasedWindowIsNotQuiet:
    """The figure an ordinance's per-day threshold is read from must not read zero."""

    def test_monitored_hours_drop_by_exactly_the_erased_overlap(self, tmp_path) -> None:
        from report.render import _coverage_hours

        with EventStore(tmp_path / "olive.db") as store:
            session_id = _session(store, BASE)
            store.update_session(
                session_id, frames_seen=1, frames_dropped=0, ended_at=BASE + 6 * HOUR
            )
            store.add_event(_event(BASE + 1 * HOUR), session_id=session_id)
            store.add_event(_event(BASE + 5 * HOUR), session_id=session_id)
            sessions, events = store.sessions(), store.events()
            before = _coverage_hours(events, store.gaps(), sessions)

            store.forget(start=WINDOW[0], end=WINDOW[1], reason="a guest")
            after = _coverage_hours(store.events(), store.gaps(), store.sessions())

        assert before is not None and after is not None
        # The window is two hours and lies wholly inside the session, so monitored
        # time drops by two and the wall clock span is unchanged.
        assert before[0] - after[0] == pytest.approx(2.0)
        assert before[1] == pytest.approx(after[1])

    def test_the_calendar_hatches_the_erased_hours_rather_than_showing_zeros(
        self, tmp_path
    ) -> None:
        from report.render import _merge_spans, _unmonitored_buckets

        with EventStore(tmp_path / "olive.db") as store:
            store.forget(start=WINDOW[0], end=WINDOW[1], reason="a guest")
            gaps = store.gaps()

        day = datetime.fromtimestamp(WINDOW[0], tz=UTC).date().isoformat()
        day_hour = {day: dict.fromkeys(range(24), 0)}
        buckets = _unmonitored_buckets(
            _merge_spans([(g.start, g.end) for g in gaps]), day_hour, UTC
        )
        touched = {
            datetime.fromtimestamp(WINDOW[0] + n * HOUR, tz=UTC).hour
            for n in range(int((WINDOW[1] - WINDOW[0]) / HOUR))
        }
        assert {hour for _day, hour in buckets} == touched
        assert buckets, "the erased hours were not marked unmonitored anywhere"


class TestTheReportDisclosesTheErasure:
    def _report(self, gaps, tz=UTC) -> str:
        from monitor.config import Config
        from report.aggregate import summarize

        return build_report(
            summarize([], quiet_hours=Config().quiet_hours, tz=tz),
            config=Config(),
            generated_at="2026-09-06 12:00 UTC",
            erased_windows=erased_window_lines(gaps, tz),
        )

    def test_it_names_the_window_and_the_reason(self, tmp_path) -> None:
        with _populated(tmp_path / "olive.db") as store:
            store.forget(start=WINDOW[0], end=WINDOW[1], reason="a guest stayed over")
            gaps = store.gaps()
        html = self._report(gaps)
        assert ERASED_HEADING in html
        assert "a guest stayed over" in html
        assert "erased" in html

    def test_it_says_no_reason_given_rather_than_leaving_a_blank(self, tmp_path) -> None:
        with _populated(tmp_path / "olive.db") as store:
            store.forget(start=WINDOW[0], end=WINDOW[1])
            gaps = store.gaps()
        assert "no reason given" in self._report(gaps)

    def test_a_report_with_no_erasure_carries_no_section(self, tmp_path) -> None:
        with _populated(tmp_path / "olive.db") as store:
            gaps = store.gaps()
        assert ERASED_HEADING not in self._report(gaps)

    def test_the_status_page_distinguishes_an_erasure_from_an_outage(self, tmp_path) -> None:
        from report.status import _gap_line

        with _populated(tmp_path / "olive.db") as store:
            store.forget(start=WINDOW[0], end=WINDOW[1], reason="a guest")
            lines = [_gap_line(g, UTC) for g in store.gaps()]

        erased = [line for line in lines if "erased by the operator" in line]
        outages = [line for line in lines if "device error" in line]
        assert len(erased) == 1 and "a guest" in erased[0]
        assert outages, "the ordinary device-error gap stopped being reported"

    def test_the_csv_marks_a_surviving_event_beside_an_erasure_unmonitored(self, tmp_path) -> None:
        """An event outside the window but overlapping a *kept* gap still reads 'no'.

        Guards the seam rather than the erasure: `_is_monitored` reads (start, end) and
        no reason, so adding a reason must not have changed what it answers.
        """
        from report.export import events_to_csv

        with EventStore(tmp_path / "olive.db") as store:
            store.forget(start=WINDOW[0], end=WINDOW[1], reason="a guest")
            gaps = store.gaps()
        out = tmp_path / "events.csv"
        events_to_csv([_event(WINDOW[0] + 60.0)], out, gaps=gaps)
        body = [
            line
            for line in out.read_text(encoding="utf-8").splitlines()
            if not line.startswith("#")
        ]
        assert body[-1].split(",")[8] == "no"


class TestTheMigrationRebuildsTheGapTable:
    def test_a_v9_database_keeps_its_gaps_and_gains_the_erased_reason(self, tmp_path) -> None:
        db = tmp_path / "olive.db"
        conn = sqlite3.connect(db)
        for script in _MIGRATIONS[:9]:
            conn.executescript(script)
        conn.execute("PRAGMA user_version = 9")
        conn.execute(
            "INSERT INTO gaps (id, session_id, start, end, reason) VALUES (5, 3, 100, 200, ?)",
            ("device-error",),
        )
        conn.commit()
        conn.close()

        with EventStore(db) as store:
            assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            kept = store.gaps()
            assert len(kept) == 1
            assert (kept[0].id, kept[0].session_id, kept[0].reason) == (5, 3, "device-error")
            assert kept[0].note is None
            assert store.integrity_ok()
            # The index the rebuild dropped with the old table is back.
            names = {
                r[0]
                for r in store._conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            }
            assert "idx_gaps_start" in names
            store.forget(start=300.0, end=400.0, reason="after the rebuild")
            assert [g.erased for g in store.gaps()] == [False, True]

    def test_the_check_still_refuses_a_reason_that_is_not_registered(self, tmp_path) -> None:
        with EventStore(tmp_path / "olive.db") as store, pytest.raises(sqlite3.IntegrityError):
            store.add_gap(0.0, 1.0, "meteor-strike")

    def test_every_registered_reason_is_accepted(self, tmp_path) -> None:
        from store import GAP_REASONS

        with EventStore(tmp_path / "olive.db") as store:
            for reason in GAP_REASONS:
                store.add_gap(0.0, 1.0, reason)
            assert {g.reason for g in store.gaps()} == set(GAP_REASONS)


class TestTheCommandLine:
    def _db(self, tmp_path) -> str:
        store = _populated(tmp_path / "olive.db")
        store.close()
        return str(tmp_path / "olive.db")

    def test_a_dry_run_prints_every_table_and_changes_nothing(self, tmp_path, capsys) -> None:
        db = self._db(tmp_path)
        with EventStore(db) as store:
            before = _snapshot(store)
        code = main(["--db", db, "--from", str(WINDOW[0]), "--to", str(WINDOW[1]), "--dry-run"])
        out = capsys.readouterr().out
        assert code == 0
        for table in ("events", "minute_levels", "clock_anomalies", "drift_advisories", "gaps"):
            assert table in out
        assert "Dry run: nothing was changed." in out
        with EventStore(db) as store:
            assert _snapshot(store) == before

    def test_it_stops_without_confirmation(self, tmp_path, capsys, monkeypatch) -> None:
        db = self._db(tmp_path)
        with EventStore(db) as store:
            before = _snapshot(store)
        monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
        code = main(["--db", db, "--from", str(WINDOW[0]), "--to", str(WINDOW[1])])
        assert code == 1
        assert "Stopped. Nothing was changed." in capsys.readouterr().out
        with EventStore(db) as store:
            assert _snapshot(store) == before

    def test_the_typed_word_erases(self, tmp_path, capsys, monkeypatch) -> None:
        db = self._db(tmp_path)
        monkeypatch.setattr("builtins.input", lambda _prompt: CONFIRMATION)
        code = main(["--db", db, "--from", str(WINDOW[0]), "--to", str(WINDOW[1]), "--reason", "g"])
        assert code == 0
        assert "not monitored" in capsys.readouterr().out
        with EventStore(db) as store:
            assert [g.note for g in store.gaps() if g.erased] == ["g"]

    def test_yes_skips_the_prompt(self, tmp_path, monkeypatch) -> None:
        db = self._db(tmp_path)

        def refuse(_prompt: str) -> str:
            raise AssertionError("--yes must not prompt")

        monkeypatch.setattr("builtins.input", refuse)
        assert main(["--db", db, "--from", str(WINDOW[0]), "--to", str(WINDOW[1]), "--yes"]) == 0

    def test_a_reversed_window_is_refused_before_anything_is_read(self, tmp_path, capsys) -> None:
        db = self._db(tmp_path)
        code = main(["--db", db, "--from", str(WINDOW[1]), "--to", str(WINDOW[0]), "--yes"])
        assert code == 2
        assert "must be after" in capsys.readouterr().err

    def test_an_unreadable_timestamp_is_refused_rather_than_guessed(self, tmp_path, capsys) -> None:
        db = self._db(tmp_path)
        code = main(["--db", db, "--from", "last night at 9:00", "--to", str(WINDOW[1])])
        assert code == 2
        assert "cannot read" in capsys.readouterr().err

    def test_a_day_with_no_time_of_day_is_refused(self, tmp_path, capsys) -> None:
        db = self._db(tmp_path)
        code = main(["--db", db, "--from", "2026-09-06", "--to", str(WINDOW[1])])
        assert code == 2
        assert "names a day, not a moment" in capsys.readouterr().err


class TestReadingAMoment:
    def test_a_naive_iso_time_is_read_in_the_configured_zone(self) -> None:
        zone = timezone(timedelta(hours=-8))
        assert (
            parse_moment("2026-09-06T21:00", zone)
            == datetime(2026, 9, 6, 21, 0, tzinfo=zone).timestamp()
        )

    def test_an_explicit_offset_wins_over_the_configured_zone(self) -> None:
        zone = timezone(timedelta(hours=-8))
        assert (
            parse_moment("2026-09-06T21:00+00:00", zone)
            == datetime(2026, 9, 6, 21, 0, tzinfo=UTC).timestamp()
        )

    def test_a_unix_timestamp_is_accepted(self) -> None:
        assert parse_moment(" 1700000000 ", UTC) == 1_700_000_000.0

    def test_a_bare_date_is_refused(self) -> None:
        """`datetime.fromisoformat` reads it happily, as midnight.

        That is the trap: accepting it would silently round the operator's window
        outward to a whole day and erase more than they asked for, and the
        acceptance would look like a feature. So a value with no time of day in it
        is refused by name rather than parsed.
        """
        for bare in ("2026-09-06", "2026-09-06T", "yesterday", ""):
            with pytest.raises(TimestampError):
                parse_moment(bare, UTC)


class TestTheSummaryNamesEveryTable:
    def test_a_zero_is_printed_rather_than_omitted(self, tmp_path) -> None:
        """A window that removed nothing must not read like one that removed
        everything except the ambient ledger."""
        with EventStore(tmp_path / "olive.db") as store:
            preview = store.forget(start=WINDOW[0], end=WINDOW[1], dry_run=True)
        lines = describe(preview, UTC)
        for table in ("events", "minute_levels", "clock_anomalies", "drift_advisories", "gaps"):
            assert any(line.strip().startswith(table) for line in lines), table
        assert any("no reason given" in line for line in lines)
