"""Minute-granular, multi-window, day-of-week quiet schedule and legacy back-compat."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pytest
from monitor.config import (
    Config,
    ConfigError,
    QuietHours,
    QuietSchedule,
    QuietWindow,
)

UTC = timezone.utc

# Weekday indices used by the schedule (0=Mon .. 6=Sun).
FRI = 4
SAT = 5


# Concrete calendar days in January 2026 (UTC), by weekday:
#   day 1 = Thursday, 2 = Friday, 3 = Saturday, 4 = Sunday, 5 = Monday.
def _dt(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


# --- minute granularity -----------------------------------------------------


def test_minute_boundaries_are_inclusive_start_exclusive_end():
    sched = QuietSchedule((QuietWindow(start_minute=22 * 60 + 30, end_minute=7 * 60),))
    # 22:29 is not yet quiet; 22:30 is (inclusive start).
    assert not sched.contains(_dt(1, 22, 29))
    assert sched.contains(_dt(1, 22, 30))
    # 06:59 is still quiet; 07:00 is not (exclusive end).
    assert sched.contains(_dt(1, 6, 59))
    assert not sched.contains(_dt(1, 7, 0))


# --- midnight wrap tied to the START day ------------------------------------


def test_wrap_membership_follows_start_day_friday():
    # Fri 23:00 -> 07:00, active only on Fridays.
    sched = QuietSchedule(
        (QuietWindow(start_minute=23 * 60, end_minute=7 * 60, days=frozenset({FRI})),)
    )
    # Sat 03:00 is quiet because the window STARTED Friday night.
    assert sched.contains(_dt(3, 3, 0))
    # Fri 23:30 (the evening portion) is quiet.
    assert sched.contains(_dt(2, 23, 30))
    # Sat 23:30 is NOT quiet: Saturday is not a start day.
    assert not sched.contains(_dt(3, 23, 30))
    # Sun 03:00 is NOT quiet: Saturday (its previous day) is not a start day.
    assert not sched.contains(_dt(4, 3, 0))


def test_wrap_membership_saturday_only_excludes_saturday_morning():
    # Same clock window but keyed to Saturday: Sat 03:00 must NOT be quiet.
    sched = QuietSchedule(
        (QuietWindow(start_minute=23 * 60, end_minute=7 * 60, days=frozenset({SAT})),)
    )
    assert not sched.contains(_dt(3, 3, 0))  # Sat morning started on Friday, not covered
    assert sched.contains(_dt(3, 23, 30))  # Sat night is covered
    assert sched.contains(_dt(4, 3, 0))  # Sun morning came from Sat night -> quiet


# --- weekday vs weekend schedules -------------------------------------------


def test_weekday_and_weekend_windows():
    weekday = QuietWindow(
        start_minute=22 * 60 + 30, end_minute=7 * 60, days=frozenset({0, 1, 2, 3, 4})
    )
    weekend = QuietWindow(start_minute=23 * 60, end_minute=8 * 60, days=frozenset({5, 6}))
    sched = QuietSchedule((weekday, weekend))
    # Thursday 22:45 -> quiet under the weekday window.
    assert sched.contains(_dt(1, 22, 45))
    # Saturday 22:45 -> NOT quiet; the weekend window only starts at 23:00.
    assert not sched.contains(_dt(3, 22, 45))
    # Saturday 23:15 -> quiet under the weekend window.
    assert sched.contains(_dt(3, 23, 15))


# --- multiple / split windows in one day ------------------------------------


def test_multiple_windows_in_a_single_day():
    nap = QuietWindow(start_minute=13 * 60, end_minute=14 * 60)
    night = QuietWindow(start_minute=22 * 60, end_minute=8 * 60)
    sched = QuietSchedule((nap, night))
    assert sched.contains(_dt(1, 13, 30))  # inside the daytime nap window
    assert not sched.contains(_dt(1, 14, 0))  # exclusive end of the nap window
    assert sched.contains(_dt(1, 23, 0))  # inside the night window
    assert not sched.contains(_dt(1, 12, 0))  # between windows


# --- labels -----------------------------------------------------------------


def test_label_covers_all_days_without_suffix():
    sched = QuietSchedule.from_legacy(22, 8)
    assert sched.label() == "22:00–08:00"


def test_label_shows_day_ranges_for_subsets():
    weekday = QuietWindow(
        start_minute=22 * 60 + 30, end_minute=7 * 60, days=frozenset({0, 1, 2, 3, 4})
    )
    weekend = QuietWindow(start_minute=23 * 60, end_minute=8 * 60, days=frozenset({5, 6}))
    sched = QuietSchedule((weekday, weekend))
    assert sched.label() == "22:30–07:00 (Mon-Fri); 23:00–08:00 (Sat-Sun)"


# --- validation errors ------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start_minute": -1, "end_minute": 100},
        {"start_minute": 0, "end_minute": 1441},
        {"start_minute": 600, "end_minute": 600},  # empty window (start == end)
    ],
)
def test_invalid_window_rejected(kwargs):
    with pytest.raises(ConfigError):
        QuietWindow(**kwargs)


def test_invalid_weekday_rejected():
    with pytest.raises(ConfigError):
        QuietWindow(start_minute=60, end_minute=120, days=frozenset({7}))


def test_empty_schedule_rejected():
    with pytest.raises(ConfigError):
        QuietSchedule(())


def test_legacy_hour_out_of_range_rejected():
    with pytest.raises(ConfigError):
        QuietSchedule.from_legacy(25, 8)
    with pytest.raises(ConfigError):
        QuietHours(start_hour=25, end_hour=8)


# --- JSON round-trips: both old and new forms -------------------------------


def test_from_json_legacy_form_warns_and_upgrades(caplog):
    with caplog.at_level(logging.WARNING, logger="monitor.config"):
        sched = QuietSchedule.from_json({"start_hour": 22, "end_hour": 8})
    assert sched == QuietSchedule.from_legacy(22, 8)
    assert any("deprecated" in r.getMessage() for r in caplog.records)


def test_from_json_new_form_roundtrips():
    data = {"windows": [{"days": [0, 1, 2, 3, 4], "start": "22:30", "end": "07:00"}]}
    sched = QuietSchedule.from_json(data)
    assert sched.contains(_dt(1, 23, 0))  # Thursday night
    # to_dict -> from_json is a stable round-trip.
    assert QuietSchedule.from_json(sched.to_dict()) == sched


def test_from_json_new_form_rejects_bad_time():
    with pytest.raises(ConfigError):
        QuietSchedule.from_json({"windows": [{"start": "24:99", "end": "07:00"}]})


def test_config_load_new_form_roundtrip(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(
        json.dumps(
            {
                "quiet_hours": {
                    "windows": [
                        {"days": [0, 1, 2, 3, 4], "start": "22:30", "end": "07:00"},
                        {"days": [5, 6], "start": "23:00", "end": "08:00"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    c = Config.load(p)
    assert len(c.quiet_hours.windows) == 2
    assert c.quiet_hours.label() == "22:30–07:00 (Mon-Fri); 23:00–08:00 (Sat-Sun)"
    # Config.to_dict emits a JSON-serializable form that reloads to the same schedule.
    reloaded = QuietSchedule.from_json(c.to_dict()["quiet_hours"])
    assert reloaded == c.quiet_hours


def test_default_schedule_matches_legacy_behavior():
    # Default = daily 22:00 -> 08:00, identical to the shipped legacy window.
    assert Config().quiet_hours == QuietHours(22, 8)
    assert Config().quiet_hours == QuietSchedule.from_legacy(22, 8)
