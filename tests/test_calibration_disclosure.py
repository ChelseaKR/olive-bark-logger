"""Events recorded before the microphone was ever calibrated are disclosed as such.

Issue #50. `_epoch_index_at` resolves a timestamp earlier than the first calibration
epoch to that first epoch — by design ("epoch 0 covers all historical rows"), so that
every level in a report sits on one scale and re-rendering never changes old numbers
(ADR-0003). What was missing was any disclosure that it happened. "Calibrate once, after
a week or two of logging" is the ordinary way the tool is used, and that single-epoch
report said "Calibrated." with no marker on the events the calibration postdates; every
row of the quiet-hours export carried the same `+48.0` whether or not the offset was in
force when the row was measured.

The fixture below is the one from the issue: two events on 1 January, one
`olive-calibrate` run on 20 January (+48.0 dB vs an Extech SL130), one event after it.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from monitor.config import Config
from monitor.detector import Event
from report.render import (
    CALIBRATION_BACK_APPLIED,
    CALIBRATION_BOOTSTRAP,
    CALIBRATION_IN_FORCE,
    CALIBRATION_NONE,
    CALIBRATION_UNSTATED,
    back_applied_summary,
    generate_report_from_db,
)
from report.render import main as report_main
from store import EventStore

JAN_1 = datetime(2026, 1, 1, 22, 0, tzinfo=timezone.utc).timestamp()
JAN_20 = datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc).timestamp()
JAN_25 = datetime(2026, 1, 25, 22, 0, tzinfo=timezone.utc).timestamp()
OFFSET = 48.0


def _ev(start: float, peak: float = -18.0) -> Event:
    return Event(start, start + 3.0, 3.0, peak, peak - 4.0)


def _issue_fixture(db) -> None:
    with EventStore(db) as store:
        store.add_event(_ev(JAN_1))
        store.add_event(_ev(JAN_1 + 3600))
        store.add_calibration(
            OFFSET,
            "vs Extech SL130 @70 dB",
            reference_instrument="Extech SL130",
            effective_from=JAN_20,
        )
        store.add_event(_ev(JAN_25, peak=-20.0))


def _data_rows(path) -> list[dict[str, str]]:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(lines))


# --- the main report ------------------------------------------------------------------


def test_single_epoch_report_discloses_events_that_predate_the_calibration(tmp_path):
    db = tmp_path / "olive.db"
    _issue_fixture(db)
    config = Config(db_path=str(db), tz="UTC")
    html = generate_report_from_db(str(db), config, generated_at="2026-02-01 00:00 UTC")

    # The numbers are unchanged: the offset IS back-applied (the issue calls that choice
    # defensible), so the January events still render as +48-shifted levels.
    assert "30.0 dBFS" in html  # -18.0 + 48.0, the loudest peak
    assert "<strong>Calibrated.</strong>" in html
    # ...and the report now says so, in the banner itself, with the count and the date.
    assert "Calibration postdates some readings." in html
    assert "2 of 3 events were recorded before the first calibration" in html
    assert "taken on 2026-01-20 12:00 UTC against Extech SL130" in html
    assert "applied to them retroactively" in html
    assert "the calibration postdates the measurement" in html
    # The methodology line carries it too, so the caveat survives a reader who skips
    # the banner.
    assert html.count("were recorded before the first calibration") >= 2


def test_multi_epoch_report_discloses_pre_first_epoch_events_as_well(tmp_path):
    """Rows before the first epoch are back-applied on the multi-epoch path exactly as
    on the single-epoch one; the epochs table alone never mentioned them."""
    db = tmp_path / "olive.db"
    _issue_fixture(db)
    with EventStore(db) as store:
        store.add_calibration(50.0, "recal", effective_from=JAN_25 - 3600)
        store.add_event(_ev(JAN_25 + 3600))
    config = Config(db_path=str(db), tz="UTC")
    html = generate_report_from_db(str(db), config, generated_at="2026-02-01 00:00 UTC")
    assert "more than one calibration epoch" in html
    assert "2 of 4 events were recorded before the first calibration" in html


def test_no_disclosure_when_every_event_follows_the_calibration(tmp_path):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        store.add_calibration(OFFSET, "cal", effective_from=JAN_1 - 60)
        store.add_event(_ev(JAN_1))
    config = Config(db_path=str(db), tz="UTC")
    html = generate_report_from_db(str(db), config, generated_at="2026-02-01 00:00 UTC")
    assert "<strong>Calibrated.</strong>" in html
    assert "before the first calibration" not in html


def test_legacy_epoch_zero_is_not_reported_as_back_applied(tmp_path):
    """The v2->v3 migration's epoch at effective_from=0 genuinely covers everything and
    has its own caveat; it must not trigger this one."""
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        store.add_calibration(OFFSET, "legacy", effective_from=0.0)
        store.add_event(_ev(JAN_1))
    assert back_applied_summary([_ev(JAN_1)], EventStore(db).calibration_history()) is None
    config = Config(db_path=str(db), tz="UTC")
    html = generate_report_from_db(str(db), config, generated_at="2026-02-01 00:00 UTC")
    assert "before the first calibration" not in html


def test_ambient_ledger_minutes_before_the_calibration_are_counted_too(tmp_path):
    from monitor.ambient import MinuteLevel

    db = tmp_path / "olive.db"
    _issue_fixture(db)
    with EventStore(db) as store:
        for i in range(3):
            store.add_minute_level(MinuteLevel(JAN_1 + 60 * i, -60.0, -50.0, -30.0, -55.0, 600))
        store.add_minute_level(MinuteLevel(JAN_25, -60.0, -50.0, -30.0, -55.0, 600))
    config = Config(db_path=str(db), tz="UTC")
    html = generate_report_from_db(str(db), config, generated_at="2026-02-01 00:00 UTC")
    assert "2 of 3 events and 3 ambient-ledger minutes were recorded before" in html


# --- the exports: every row says whether its offset was in force -----------------------


def test_exports_mark_each_row_in_force_or_back_applied(tmp_path):
    db = tmp_path / "olive.db"
    _issue_fixture(db)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"db_path": str(db), "tz": "UTC"}))
    out = tmp_path / "report.html"
    events_csv = tmp_path / "events.csv"
    v_csv = tmp_path / "violations.csv"
    v_html = tmp_path / "violations.html"
    assert (
        report_main(
            [
                "--config",
                str(cfg),
                "--out",
                str(out),
                "--csv",
                str(events_csv),
                "--violations-csv",
                str(v_csv),
                "--violations-html",
                str(v_html),
            ]
        )
        == 0
    )

    for path in (events_csv, v_csv):
        rows = _data_rows(path)
        assert [r["calibration_offset_db"] for r in rows] == ["+48.0", "+48.0", "+48.0"]
        assert [r["calibration_basis"] for r in rows] == [
            CALIBRATION_BACK_APPLIED,
            CALIBRATION_BACK_APPLIED,
            CALIBRATION_IN_FORCE,
        ]

    html = v_html.read_text(encoding="utf-8")
    assert '<th scope="col">Offset basis</th>' in html
    assert html.count(f"<td>{CALIBRATION_BACK_APPLIED}</td>") == 2
    assert html.count(f"<td>{CALIBRATION_IN_FORCE}</td>") == 1
    assert "Calibration postdates some readings: 2 of 3 events were recorded before" in html


def test_basis_when_there_is_no_calibration_history(tmp_path):
    from report.export import events_to_csv

    events = [_ev(JAN_1)]
    raw = tmp_path / "raw.csv"
    events_to_csv(events, raw, tz=timezone.utc)
    assert _data_rows(raw)[0]["calibration_basis"] == CALIBRATION_NONE

    # Offsets given but no basis: the export must not guess.
    unstated = tmp_path / "unstated.csv"
    events_to_csv(events, unstated, tz=timezone.utc, offsets_db=[5.0])
    assert _data_rows(unstated)[0]["calibration_basis"] == CALIBRATION_UNSTATED

    # The deprecated config bootstrap offset is named as such through the CLI.
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        store.add_event(_ev(JAN_1))
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"db_path": str(db), "tz": "UTC", "calibration_offset": 7.0}))
    boot = tmp_path / "boot.csv"
    report_main(["--config", str(cfg), "--out", str(tmp_path / "r.html"), "--csv", str(boot)])
    assert _data_rows(boot)[0]["calibration_basis"] == CALIBRATION_BOOTSTRAP
