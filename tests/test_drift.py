"""The advisory drift watch (EXP-04), and the absence it must not render as a value.

Two families of test here. The first is the feature: an 8 dB move raises exactly one
advisory with the right sign, a 2 dB move raises none. The second is the failure mode
this repository keeps finding in its own code -- a check that could not run reporting
the same thing as a check that ran and found nothing -- and it is asserted at every
layer the state passes through: the comparison, the heartbeat, the status page and the
report.
"""

from __future__ import annotations

import json
from datetime import timezone

import pytest
from monitor import drift
from monitor.ambient import MinuteLevel
from monitor.config import Config, ConfigError
from monitor.detector import Event
from monitor.service import DriftWatch, _health_payload, drift_health_fields
from report.aggregate import summarize
from report.render import build_report, generate_report_from_db
from report.status import (
    DRIFT_HEADING,
    StatusAggregates,
    collect_status_aggregates,
    render_status,
)
from store import EventStore

HOUR = 3600.0
DAY = 86400.0
BASE = 1_700_000_000.0


def _minutes(start: float, count: int, level: float) -> list[MinuteLevel]:
    """`count` consecutive minutes all sitting at the same ambient level."""
    return [
        MinuteLevel(
            minute_start=start + 60.0 * i,
            min_dbfs=level - 2.0,
            median_dbfs=level,
            max_dbfs=level + 2.0,
            l90_dbfs=level - 1.0,
            frame_count=600,
        )
        for i in range(count)
    ]


def _baseline(level: float, count: int = 60) -> drift.AmbientBaseline | None:
    return drift.summarize_baseline(_minutes(BASE, count, level))


def _windows() -> tuple[tuple[float, float], tuple[float, float]]:
    return (BASE, BASE + DAY), (BASE + 2 * DAY, BASE + 3 * DAY)


def _compare(reference: float, recent: float, *, tolerance: float = 5.0) -> drift.DriftCheck:
    ref_window, rec_window = _windows()
    return drift.compare_baselines(
        _baseline(reference),
        _baseline(recent),
        calibration_epoch=BASE,
        reference_window=ref_window,
        recent_window=rec_window,
        tolerance_db=tolerance,
    )


# --- the feature -------------------------------------------------------------------


def test_an_eight_db_rise_raises_one_advisory_with_the_right_sign() -> None:
    check = _compare(-50.0, -42.0)
    assert check.status == drift.ADVISORY
    assert check.advisory is not None
    assert check.advisory.median_delta_db == pytest.approx(8.0)
    assert check.advisory.l90_delta_db == pytest.approx(8.0)
    assert check.advisory.largest_delta_db > 0, "the room got louder; the sign must say so"


def test_an_eight_db_fall_raises_an_advisory_with_a_negative_sign() -> None:
    check = _compare(-42.0, -50.0)
    assert check.status == drift.ADVISORY
    assert check.advisory is not None
    assert check.advisory.largest_delta_db == pytest.approx(-8.0)


def test_a_two_db_move_raises_none() -> None:
    check = _compare(-50.0, -48.0)
    assert check.status == drift.STEADY
    assert check.advisory is None
    # Steady still carries the comparison it made, so "steady" is checkable.
    assert check.reference is not None and check.recent is not None


def test_a_move_exactly_at_the_tolerance_is_steady() -> None:
    """The boundary is inclusive on the steady side, matching ClockGuard's tolerance."""
    check = _compare(-50.0, -45.0, tolerance=5.0)
    assert check.status == drift.STEADY


def test_the_l90_can_trip_the_watch_on_its_own() -> None:
    """A room whose median holds while its floor rises has still drifted."""
    ref_window, rec_window = _windows()
    reference = drift.AmbientBaseline(minute_count=60, median_dbfs=-50.0, l90_dbfs=-60.0)
    recent = drift.AmbientBaseline(minute_count=60, median_dbfs=-50.0, l90_dbfs=-50.0)
    check = drift.compare_baselines(
        reference,
        recent,
        calibration_epoch=BASE,
        reference_window=ref_window,
        recent_window=rec_window,
        tolerance_db=5.0,
    )
    assert check.status == drift.ADVISORY
    assert check.advisory is not None
    assert check.advisory.median_delta_db == pytest.approx(0.0)
    assert check.advisory.largest_delta_db == pytest.approx(10.0)


def test_the_l90_percentile_rank_matches_the_ambient_ledger() -> None:
    """Two modules computing "L90" by two different rules would be a silent divergence."""
    from monitor.ambient import _L90_PERCENTILE_RANK

    assert drift.L90_PERCENTILE_RANK == _L90_PERCENTILE_RANK


# --- absence is not a value --------------------------------------------------------


def test_an_empty_window_has_no_baseline_rather_than_a_zero_one() -> None:
    assert drift.summarize_baseline([]) is None


@pytest.mark.parametrize(
    ("reference", "recent", "epoch", "ledger", "reason"),
    [
        (_baseline(-50.0), _baseline(-50.0), BASE, False, drift.REASON_LEDGER_DISABLED),
        (_baseline(-50.0), _baseline(-50.0), None, True, drift.REASON_NO_CALIBRATION),
        (None, _baseline(-50.0), BASE, True, drift.REASON_NO_REFERENCE),
        (_baseline(-50.0), None, BASE, True, drift.REASON_NO_RECENT),
    ],
)
def test_every_uncomparable_case_is_unavailable_with_a_reason(
    reference: drift.AmbientBaseline | None,
    recent: drift.AmbientBaseline | None,
    epoch: float | None,
    ledger: bool,
    reason: str,
) -> None:
    ref_window, rec_window = _windows()
    check = drift.compare_baselines(
        reference,
        recent,
        calibration_epoch=epoch,
        reference_window=ref_window,
        recent_window=rec_window,
        tolerance_db=5.0,
        ledger_enabled=ledger,
    )
    assert check.status == drift.UNAVAILABLE
    assert check.reason == reason
    assert check.advisory is None
    assert not check.ran
    # The point of the whole design: the words differ from the steady case.
    assert check.status != drift.STEADY


def test_a_recent_calibration_refuses_to_compare_a_window_against_itself() -> None:
    """Overlapping windows would produce a small delta whatever the microphone did."""
    with EventStore(":memory:") as store:
        for minute in _minutes(BASE, 60, -50.0):
            store.add_minute_level(minute, session_id=None)
        check = drift.evaluate(
            store,
            calibration_epoch=BASE + 12 * HOUR,
            now=BASE + 20 * HOUR,
            window_hours=24.0,
            tolerance_db=5.0,
            ledger_enabled=True,
        )
    assert check.status == drift.UNAVAILABLE
    assert check.reason == drift.REASON_WINDOWS_OVERLAP


# --- the store and the watch -------------------------------------------------------


def _store_with_drift(path, *, reference: float, recent: float) -> EventStore:
    store = EventStore(path)
    store.add_calibration(0.0, "fixture", effective_from=BASE)
    for minute in _minutes(BASE, 60, reference):
        store.add_minute_level(minute, session_id=None)
    for minute in _minutes(BASE + 3 * DAY, 60, recent):
        store.add_minute_level(minute, session_id=None)
    return store


def _config(**overrides: object) -> Config:
    base: dict[str, object] = {
        "tz": "UTC",
        "ambient_ledger": True,
        "drift_tolerance_db": 5.0,
        "drift_window_hours": 24.0,
    }
    base.update(overrides)
    return Config(**base)  # type: ignore[arg-type]


def test_the_watch_records_exactly_one_advisory_for_a_drifted_store(tmp_path) -> None:
    now = BASE + 4 * DAY
    with _store_with_drift(tmp_path / "olive.db", reference=-50.0, recent=-42.0) as store:
        watch = DriftWatch(_config())
        check = watch.run(store, now=now, session_id=None)
        assert check is not None and check.status == drift.ADVISORY
        assert len(store.drift_advisories()) == 1
        row = store.drift_advisories()[0]
        assert row.median_delta_db == pytest.approx(8.0)
        assert row.calibration_epoch == BASE


def test_a_steady_store_records_nothing_and_still_reports_that_it_looked(tmp_path) -> None:
    now = BASE + 4 * DAY
    with _store_with_drift(tmp_path / "olive.db", reference=-50.0, recent=-48.0) as store:
        watch = DriftWatch(_config())
        check = watch.run(store, now=now, session_id=None)
        assert check is not None and check.status == drift.STEADY
        assert store.drift_advisories() == []


def test_the_watch_does_not_rerun_or_duplicate_inside_its_interval(tmp_path) -> None:
    now = BASE + 4 * DAY
    with _store_with_drift(tmp_path / "olive.db", reference=-50.0, recent=-42.0) as store:
        watch = DriftWatch(_config(), interval_s=DAY)
        assert watch.run(store, now=now, session_id=None) is not None
        # Not due: None, which is distinct from "compared and found nothing".
        assert watch.run(store, now=now + HOUR, session_id=None) is None
        assert len(store.drift_advisories()) == 1

        # A fresh process (a monitor restart) is due immediately, but the store-level
        # dedupe keeps it from writing a second row for the same epoch within a day.
        restarted = DriftWatch(_config(), interval_s=DAY)
        assert restarted.run(store, now=now + HOUR, session_id=None) is not None
        assert len(store.drift_advisories()) == 1

        # A day later the condition is reported again: it is still true, and a reader
        # of the ledger should see that it persisted rather than that it happened once.
        for minute in _minutes(now + DAY, 60, -42.0):
            store.add_minute_level(minute, session_id=None)
        later = DriftWatch(_config(), interval_s=DAY)
        assert later.run(store, now=now + DAY + HOUR, session_id=None) is not None
        assert len(store.drift_advisories()) == 2


def test_an_advisory_changes_no_event_and_no_count(tmp_path) -> None:
    """Advisory means advisory: ADR 0030. Nothing about the record may move."""
    db = tmp_path / "olive.db"
    with _store_with_drift(db, reference=-50.0, recent=-42.0) as store:
        for hour in (2, 23):
            store.add_event(
                Event(BASE + hour * HOUR, BASE + hour * HOUR + 4.0, 4.0, -10.0, -14.0),
                session_id=None,
            )
        before = [(e.start, e.end, e.duration, e.peak_level, e.avg_level) for e in store.events()]
        before_minutes = [m.minute_start for m in store.minute_levels()]
        DriftWatch(_config()).run(store, now=BASE + 4 * DAY, session_id=None)
        after = [(e.start, e.end, e.duration, e.peak_level, e.avg_level) for e in store.events()]
        assert after == before
        assert [m.minute_start for m in store.minute_levels()] == before_minutes
        # And the configured detection parameters are untouched.
        assert _config().threshold_dbfs == Config().threshold_dbfs


def test_the_watch_with_the_ledger_off_reports_unavailable_not_steady(tmp_path) -> None:
    with _store_with_drift(tmp_path / "olive.db", reference=-50.0, recent=-42.0) as store:
        check = DriftWatch(_config(ambient_ledger=False)).run(
            store, now=BASE + 4 * DAY, session_id=None
        )
    assert check is not None
    assert check.status == drift.UNAVAILABLE
    assert check.reason == drift.REASON_LEDGER_DISABLED


# --- the heartbeat -----------------------------------------------------------------


def test_the_heartbeat_distinguishes_all_four_drift_states() -> None:
    assert drift_health_fields(None)["drift_status"] == "not-yet-checked"
    unavailable = drift_health_fields(
        drift.DriftCheck(status=drift.UNAVAILABLE, reason=drift.REASON_LEDGER_DISABLED)
    )
    assert unavailable["drift_status"] == drift.UNAVAILABLE
    assert unavailable["drift_reason"] == drift.REASON_LEDGER_DISABLED
    assert "drift_median_delta_db" not in unavailable

    steady = drift_health_fields(_compare(-50.0, -48.0))
    assert steady["drift_status"] == drift.STEADY
    assert steady["drift_median_delta_db"] == pytest.approx(2.0)

    advisory = drift_health_fields(_compare(-50.0, -42.0))
    assert advisory["drift_status"] == drift.ADVISORY
    assert advisory["drift_tolerance_db"] == pytest.approx(5.0)


def test_the_heartbeat_stays_json_and_carries_no_identifying_text() -> None:
    """The existing heartbeat gate (tests/test_health.py) with the new fields on it."""
    from monitor.health import CaptureStats

    payload = _health_payload(
        _config(db_path="olive.db"),
        CaptureStats(frames_seen=10, frames_dropped=0),
        started_at=BASE,
        now=BASE + 60,
        session_id=1,
        drift=_compare(-50.0, -42.0),
    )
    text = json.dumps(payload)
    assert json.loads(text) == payload
    # Every drift value is a number or one of the module's own fixed strings.
    for key, value in payload.items():
        if not key.startswith("drift_"):
            continue
        assert isinstance(value, (int, float, str))
        if isinstance(value, str):
            assert value in {
                drift.STEADY,
                drift.ADVISORY,
                drift.UNAVAILABLE,
                "not-yet-checked",
                drift.REASON_LEDGER_DISABLED,
                drift.REASON_NO_CALIBRATION,
                drift.REASON_NO_REFERENCE,
                drift.REASON_NO_RECENT,
                drift.REASON_WINDOWS_OVERLAP,
            }


# --- the status page ---------------------------------------------------------------


def _status_html(payload: dict[str, object]) -> str:
    aggregates = StatusAggregates(
        summary=summarize([], quiet_hours=_config().quiet_hours, tz=timezone.utc),
        quiet_window="22:00-08:00",
        tz_name="UTC",
        gaps=[],
        off_air=[],
    )
    return render_status(payload, aggregates, now=BASE)


def test_the_status_page_says_unavailable_rather_than_omitting_the_block() -> None:
    html = _status_html({"updated_at": BASE})
    assert DRIFT_HEADING in html
    assert "not yet checked in this run" in html


def test_the_status_page_prints_the_reason_and_the_action() -> None:
    unavailable = _status_html(
        {
            "updated_at": BASE,
            **drift_health_fields(
                drift.DriftCheck(status=drift.UNAVAILABLE, reason=drift.REASON_LEDGER_DISABLED)
            ),
        }
    )
    assert drift.REASON_LEDGER_DISABLED in unavailable
    assert "re-run `olive-calibrate`" not in unavailable.lower()

    advisory = _status_html({"updated_at": BASE, **drift_health_fields(_compare(-50.0, -42.0))})
    assert "advisory: the ambient baseline has moved past the tolerance" in advisory
    assert "Re-run `olive-calibrate`" in advisory
    assert "+8.0 dB" in advisory


def test_the_status_page_collects_without_a_drift_payload(tmp_path) -> None:
    """collect_status_aggregates is untouched by this feature and must stay so."""
    with EventStore(tmp_path / "olive.db") as store:
        aggregates = collect_status_aggregates(store, _config(), now=BASE)
    assert aggregates.gaps == []


# --- the report --------------------------------------------------------------------


def _report_html(store_path, config: Config) -> str:
    return generate_report_from_db(str(store_path), config, generated_at="2026-01-01 00:00 UTC")


def test_the_report_says_unavailable_when_the_ambient_ledger_is_disabled(tmp_path) -> None:
    """The acceptance criterion from the issue, worded as the issue words it."""
    db = tmp_path / "olive.db"
    with _store_with_drift(db, reference=-50.0, recent=-42.0):
        pass
    html = _report_html(db, _config(ambient_ledger=False))
    assert "Drift watch unavailable: ambient ledger not enabled" in html
    assert "has not moved more than the configured tolerance" not in html


def test_the_report_discloses_a_drifted_baseline(tmp_path) -> None:
    db = tmp_path / "olive.db"
    with _store_with_drift(db, reference=-50.0, recent=-42.0):
        pass
    html = _report_html(db, _config())
    assert "Ambient baseline moved +8.0 dB (up) since calibration on" in html
    assert "re-run" in html
    assert "advisory: no detection parameter was changed" in html


def test_the_report_states_a_steady_baseline_as_a_finding(tmp_path) -> None:
    db = tmp_path / "olive.db"
    with _store_with_drift(db, reference=-50.0, recent=-48.0):
        pass
    html = _report_html(db, _config())
    assert "has not moved more than the configured tolerance" in html
    assert "Drift watch unavailable" not in html


def test_a_report_rendered_without_a_check_never_claims_steady() -> None:
    """build_report's default. A caller that forgets must not publish reassurance."""
    summary = summarize([], quiet_hours=Config().quiet_hours, tz=timezone.utc)
    html = build_report(summary, config=_config(), generated_at="2026-01-01 00:00 UTC")
    assert "Drift watch unavailable" in html
    assert "has not moved more than the configured tolerance" not in html


def test_the_report_reports_recorded_advisories_as_history_not_as_the_finding(
    tmp_path,
) -> None:
    """A stored advisory is what the monitor saw then; the block's verdict is now."""
    db = tmp_path / "olive.db"
    with _store_with_drift(db, reference=-50.0, recent=-48.0) as store:
        DriftWatch(_config()).run(store, now=BASE + 4 * DAY, session_id=None)
        store.add_drift_advisory(
            drift.DriftAdvisory(
                calibration_epoch=BASE,
                reference_start=BASE,
                reference_end=BASE + DAY,
                recent_start=BASE + 2 * DAY,
                recent_end=BASE + 3 * DAY,
                reference_minutes=60,
                recent_minutes=60,
                median_delta_db=9.0,
                l90_delta_db=9.0,
                tolerance_db=5.0,
            ),
            session_id=None,
            detected_at=BASE + 3 * DAY,
        )
    html = _report_html(db, _config())
    assert "The monitor recorded 1 drift advisory during this window." in html
    # The store is steady now, and the block says so rather than inheriting the row.
    assert "has not moved more than the configured tolerance" in html


# --- config ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"drift_tolerance_db": 0.0},
        {"drift_tolerance_db": -1.0},
        {"drift_window_hours": 0.0},
        {"drift_check_interval_s": 0.0},
    ],
)
def test_a_non_positive_drift_setting_is_refused(override: dict[str, float]) -> None:
    """A zero tolerance or a zero window would make the watch a no-op with a status."""
    with pytest.raises(ConfigError):
        _config(**override)


def test_the_drift_defaults_are_the_documented_ones() -> None:
    config = Config()
    assert config.drift_tolerance_db == 5.0
    assert config.drift_window_hours == 24.0
    assert config.drift_check_interval_s == 86400.0
    assert config.ambient_ledger is False, "the watch's input stays opt-in"
