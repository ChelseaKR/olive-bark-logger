"""Config loading, defaults, and quiet-hours window logic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from monitor.config import Config, ConfigError, QuietHours


def test_defaults_load_without_file():
    c = Config.load(None)
    assert c.threshold_dbfs == -35.0
    # The default quiet schedule is the legacy daily 22:00 -> 08:00 window.
    assert c.quiet_hours.label() == "22:00–08:00"  # noqa: RUF001 - intentional en dash


def test_load_from_json(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(
        json.dumps({"threshold_dbfs": -40, "quiet_hours": {"start_hour": 21, "end_hour": 7}})
    )
    c = Config.load(p)
    assert c.threshold_dbfs == -40
    # The legacy hour form auto-upgrades to a single-window schedule.
    assert c.quiet_hours.label() == "21:00–07:00"  # noqa: RUF001 - intentional en dash


def test_loads_opt_in_ipc_socket(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"ipc_socket": "/run/olive/ipc.sock"}))
    assert Config.load(path).ipc_socket == "/run/olive/ipc.sock"


def test_missing_file_falls_back_to_defaults(tmp_path):
    c = Config.load(tmp_path / "nope.json")
    assert c.threshold_dbfs == -35.0


def test_quiet_hours_wrapping_midnight():
    qh = QuietHours(start_hour=22, end_hour=8)
    in_quiet = datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)
    in_quiet2 = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
    not_quiet = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert qh.contains(in_quiet)
    assert qh.contains(in_quiet2)
    assert not qh.contains(not_quiet)


def test_quiet_hours_non_wrapping():
    qh = QuietHours(start_hour=1, end_hour=5)
    assert qh.contains(datetime(2026, 1, 1, 3, tzinfo=timezone.utc))
    assert not qh.contains(datetime(2026, 1, 1, 6, tzinfo=timezone.utc))


def test_invalid_hour_rejected():
    with pytest.raises(ValueError):
        QuietHours(start_hour=25, end_hour=8)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sample_rate": 0},
        {"frame_size": -1},
        {"min_duration_s": -0.1},
        {"debounce_s": -1},
        {"threshold_dbfs": 5.0},
        {"threshold_dbfs": -250.0},
        {"retention_days": -1},
    ],
)
def test_invalid_config_values_rejected(kwargs):
    with pytest.raises(ConfigError):
        Config(**kwargs)


def test_unknown_config_key_rejected(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"not_a_real_key": 1}))
    with pytest.raises(ConfigError):
        Config.load(p)


def test_tzinfo_resolves_iana_zone():
    zi = pytest.importorskip("zoneinfo")
    try:
        zi.ZoneInfo("America/Los_Angeles")
    except zi.ZoneInfoNotFoundError:  # pragma: no cover - host without tzdata
        pytest.skip("tzdata not available")
    tz = Config(tz="America/Los_Angeles").tzinfo()
    assert "Los_Angeles" in str(tz)


def test_tzinfo_falls_back_to_utc_for_bad_zone():
    tz = Config(tz="Not/ARealZone").tzinfo()
    assert tz.utcoffset(datetime(2026, 1, 1)) == timedelta(0)


def test_to_dict_includes_new_fields():
    d = Config(tz="UTC", retention_days=7).to_dict()
    assert d["tz"] == "UTC"
    assert d["retention_days"] == 7


def test_status_path_derives_from_health_path_or_uses_explicit_path(tmp_path):
    health = tmp_path / "health.json"
    assert Config(health_path=str(health)).status_html_path() == str(tmp_path / "status.html")
    explicit = tmp_path / "ops.html"
    assert Config(health_path=str(health), status_path=str(explicit)).status_html_path() == str(
        explicit
    )
    assert Config().status_html_path() == ""


def test_defaults_to_text_log_format():
    assert Config.load(None).log_format == "text"


def test_loads_json_log_format(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"log_format": "json"}))
    assert Config.load(path).log_format == "json"


def test_invalid_log_format_rejected():
    with pytest.raises(ConfigError):
        Config(log_format="yaml")
