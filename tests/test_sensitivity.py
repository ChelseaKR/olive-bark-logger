"""Merge-blocking: the threshold-sensitivity exhibit (EXP-03) answers what it can, and
says so where it cannot.

The section exists to pre-empt "you picked the threshold that flatters you". A sensitivity
analysis that quietly prints a derived-looking number where the stored data cannot support
one would make that attack *worse*, not better, so most of this file is about the places a
number must not appear:

* below the configured threshold the event column is a floor, never a count -- every
  recorded event clears any lower threshold, so a count there is arithmetic dressed as a
  recomputation, and a flat column in a sensitivity table reads as "insensitive";
* with no ambient ledger the section says it could not be computed, rather than rendering
  a table of zeros or vanishing (either would read as "tested, and nothing moved");
* the recount runs on the raw dBFS scale detection used, not the calibrated scale the
  report shows a reader, because `threshold_dbfs` is defined against the stored scale
  (ADR-0003) and adjusting one side of the comparison moves every row.

The two fixtures the issue asks for are here as
`test_a_pattern_well_clear_of_ambient_survives_six_db` and
`test_a_pattern_barely_clear_of_ambient_collapses_at_plus_three`, and both assert the
headline count is untouched in the same breath.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from monitor.ambient import MinuteLevel
from monitor.config import Config
from monitor.detector import Event
from report.aggregate import summarize
from report.render import build_report, generate_report_from_db
from report.render import main as report_main
from report.sensitivity import (
    SENSITIVITY_APPROXIMATION_NOTE,
    SENSITIVITY_DELTAS_DB,
    SENSITIVITY_FLOOR_NOTE,
    SENSITIVITY_SCALE_NOTE,
    SENSITIVITY_UNAVAILABLE_NOTE,
    sensitivity,
)
from store import EventStore

DAY = datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp()
THRESHOLD = -35.0
SECTION_HEADING = "<h2>Threshold sensitivity</h2>"


def _event(offset_s: float, peak: float) -> Event:
    return Event(
        start=DAY + offset_s,
        end=DAY + offset_s + 3.0,
        duration=3.0,
        peak_level=peak,
        avg_level=peak - 4.0,
    )


def _minute(index: int, max_dbfs: float, *, floor: float = -70.0) -> MinuteLevel:
    return MinuteLevel(
        minute_start=DAY + index * 60.0,
        min_dbfs=floor,
        median_dbfs=floor + 5.0,
        max_dbfs=max_dbfs,
        l90_dbfs=floor + 2.0,
        frame_count=600,
    )


def _row(result, delta: float):
    return next(r for r in result.rows if r.delta_db == delta)


# --- the two fixtures the exhibit exists to distinguish ---------------------------------


def test_a_pattern_well_clear_of_ambient_survives_six_db():
    """Ambient sits ~20 dB below the events, so moving the threshold changes nothing.

    This is the case the section is meant to *support*: the counts hold at +6 dB, which is
    evidence the pattern is not an artifact of where the threshold was put.
    """
    events = [_event(i * 600, peak=-15.0) for i in range(4)]
    minutes = [_minute(i, max_dbfs=-15.0 if i % 10 == 0 else -55.0) for i in range(40)]

    result = sensitivity(events, minutes, threshold_dbfs=THRESHOLD)

    assert [_row(result, d).events_at_or_above for d in (0.0, 3.0, 6.0)] == [4, 4, 4]
    assert _row(result, 6.0).loud_minutes == _row(result, 0.0).loud_minutes
    # Lowering the threshold by 6 dB does not sweep in a crowd of near-misses either: the
    # ledger, which *can* answer downward, says the same minutes are loud.
    assert _row(result, -6.0).loud_minutes == _row(result, 0.0).loud_minutes
    assert result.headline_event_count == 4


def test_a_pattern_barely_clear_of_ambient_collapses_at_plus_three():
    """Events peak 2 dB over ambient: at +3 dB nothing is left, and the table shows it."""
    events = [_event(i * 600, peak=-33.0) for i in range(4)]
    minutes = [_minute(i, max_dbfs=-33.0 if i % 10 == 0 else -35.0) for i in range(40)]

    result = sensitivity(events, minutes, threshold_dbfs=THRESHOLD)

    assert _row(result, 0.0).events_at_or_above == 4
    assert _row(result, 3.0).events_at_or_above == 0, "a 2 dB margin cannot survive +3 dB"
    assert _row(result, 6.0).events_at_or_above == 0
    assert _row(result, 3.0).loud_minutes == 0
    # And the headline is the same measured number as in the confident case above: the
    # exhibit changes what a reader can conclude, never what was measured.
    assert result.headline_event_count == 4


def test_the_headline_counts_do_not_move_when_the_section_is_added():
    """The whole claim of the section rests on this. Rendered with and without it, every
    number outside the section is byte-identical -- so the exhibit cannot be suspected of
    feeding back into the counts it is commenting on."""
    config = Config(tz="UTC", threshold_dbfs=THRESHOLD)
    events = [_event(i * 600, peak=-15.0) for i in range(4)]
    summary = summarize(events, quiet_hours=config.quiet_hours, tz=config.tzinfo())
    minutes = [_minute(i, max_dbfs=-15.0 if i % 10 == 0 else -55.0) for i in range(40)]

    without = build_report(summary, config=config, generated_at="2026-04-01 12:00 UTC")
    with_section = build_report(
        summary,
        config=config,
        generated_at="2026-04-01 12:00 UTC",
        sensitivity_result=sensitivity(events, minutes, threshold_dbfs=THRESHOLD),
    )

    assert SECTION_HEADING not in without
    assert SECTION_HEADING in with_section
    head, _, tail = with_section.partition(SECTION_HEADING)
    rest = tail.split("\n\n", 1)[1] if "\n\n" in tail else ""
    assert head in without and (not rest or rest in without), (
        "adding the sensitivity section changed text outside it; the headline numbers and "
        "every other section must be untouched"
    )


# --- the places a number must not appear ------------------------------------------------


def test_below_the_configured_threshold_the_event_column_is_a_floor_not_a_count():
    events = [_event(i * 600, peak=-15.0) for i in range(4)]
    minutes = [_minute(i, max_dbfs=-15.0 if i % 10 == 0 else -55.0) for i in range(40)]
    result = sensitivity(events, minutes, threshold_dbfs=THRESHOLD)

    below = [r for r in result.rows if r.delta_db < 0]
    assert below, "the deltas no longer include a threshold below the configured one"
    assert all(r.events_at_or_above is None for r in below), (
        "a lower threshold got an event count. Every recorded event clears it by "
        "construction, so any number there equals the headline and reads as 'insensitive' "
        "-- see report/sensitivity.py"
    )
    # ...and the ledger still answers, so the row is not blank either.
    assert all(r.loud_minutes >= 0 for r in below)

    html = build_report(
        summarize(events, quiet_hours=Config(tz="UTC").quiet_hours),
        config=Config(tz="UTC", threshold_dbfs=THRESHOLD),
        generated_at="2026-04-01 12:00 UTC",
        sensitivity_result=result,
    )
    section = html.split(SECTION_HEADING, 1)[1].split("</table>", 1)[0]
    assert f"at least {result.headline_event_count} (not recorded)" in section
    assert SENSITIVITY_FLOOR_NOTE in section


def test_without_an_ambient_ledger_the_section_says_so_rather_than_showing_zeros(tmp_path):
    """The absence-as-a-value case, in the section built to argue the record is honest.

    A table of zeros would say "we checked and the threshold does not matter". An omitted
    section would leave a reader unable to tell that from "we never checked". Neither is
    what this record can support, so it says which one it is.
    """
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for i in range(4):
            store.add_event(_event(i * 600, peak=-15.0))

    html = generate_report_from_db(
        str(db), Config(tz="UTC", threshold_dbfs=THRESHOLD), generated_at="2026-04-01 12:00 UTC"
    )

    assert SECTION_HEADING in html
    section = html.split(SECTION_HEADING, 1)[1].split("<h2>", 1)[0]
    assert SENSITIVITY_UNAVAILABLE_NOTE in section
    assert "<table" not in section, "an unavailable analysis rendered a table anyway"
    assert not re.search(r"<td>\s*0\s*</td>", section), "rendered a zero where it has no datum"


def test_sensitivity_off_omits_the_section_entirely(tmp_path):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for i in range(4):
            store.add_event(_event(i * 600, peak=-15.0))
            store.add_minute_level(_minute(i, max_dbfs=-15.0))

    config = Config(tz="UTC", threshold_dbfs=THRESHOLD)
    on = generate_report_from_db(str(db), config, generated_at="2026-04-01 12:00 UTC")
    off = generate_report_from_db(
        str(db), config, generated_at="2026-04-01 12:00 UTC", include_sensitivity=False
    )

    assert SECTION_HEADING in on
    assert SECTION_HEADING not in off
    assert SENSITIVITY_UNAVAILABLE_NOTE not in off, (
        "'off' must omit the section, not render its unavailable note -- a reader who "
        "turned it off is not being told the analysis failed"
    )


def test_the_cli_flag_reaches_the_report(tmp_path, capsys):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        store.add_event(_event(0, peak=-15.0))
        store.add_minute_level(_minute(0, max_dbfs=-15.0))
    out = tmp_path / "report.html"
    cfg = tmp_path / "config.json"
    cfg.write_text(f'{{"db_path": "{db}", "tz": "UTC", "threshold_dbfs": {THRESHOLD}}}')

    assert report_main(["--config", str(cfg), "--out", str(out), "--generated-at", "t"]) == 0
    assert SECTION_HEADING in out.read_text(encoding="utf-8")
    capsys.readouterr()

    assert (
        report_main(
            [
                "--config",
                str(cfg),
                "--out",
                str(out),
                "--generated-at",
                "t",
                "--sensitivity",
                "off",
            ]
        )
        == 0
    )
    assert SECTION_HEADING not in out.read_text(encoding="utf-8")
    capsys.readouterr()


# --- scale, determinism, accessibility ---------------------------------------------------


def test_the_recount_runs_on_the_raw_scale_detection_used(tmp_path):
    """`threshold_dbfs` is compared against raw stored dBFS; calibration is a render-time
    presentation offset (ADR-0003). If the recount used the calibrated levels the report
    displays, a +12 dB calibration would silently push every event over every alternative
    threshold and the exhibit would report a robustness the record does not have."""
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for i in range(4):
            store.add_event(_event(i * 600, peak=-33.0))  # 2 dB over the threshold, raw
            store.add_minute_level(_minute(i, max_dbfs=-33.0))
        store.add_calibration(12.0, "bench reference", effective_from=DAY - 3600)

    html = generate_report_from_db(
        str(db), Config(tz="UTC", threshold_dbfs=THRESHOLD), generated_at="2026-04-01 12:00 UTC"
    )
    section = html.split(SECTION_HEADING, 1)[1].split("</table>", 1)[0]

    assert f"{THRESHOLD:.1f} dBFS" in section, "the configured row is not on the raw scale"
    assert SENSITIVITY_SCALE_NOTE in section, "the scale the table uses is not disclosed"
    # 2 dB of headroom, so +3 dB must still empty the table despite the +12 dB calibration.
    rows = re.findall(r"<tr><th scope=\"row\">([^<]+)</th>(.*?)</tr>", section)
    plus_three = next(cells for label, cells in rows if label.startswith("+3"))
    assert "<td>0</td>" in plus_three, (
        "a +12 dB calibration offset leaked into the recount: events 2 dB over the raw "
        "threshold are reported as surviving +3 dB"
    )


def test_the_section_is_deterministic(tmp_path):
    db = tmp_path / "olive.db"
    with EventStore(db) as store:
        for i in range(6):
            store.add_event(_event(i * 600, peak=-15.0 - i))
            store.add_minute_level(_minute(i, max_dbfs=-20.0 - i))

    config = Config(tz="UTC", threshold_dbfs=THRESHOLD)
    first = generate_report_from_db(str(db), config, generated_at="fixed")
    second = generate_report_from_db(str(db), config, generated_at="fixed")
    assert first == second
    assert first.split(SECTION_HEADING, 1)[1] == second.split(SECTION_HEADING, 1)[1]


def test_the_table_is_accessible_and_carries_its_caveat():
    events = [_event(i * 600, peak=-15.0) for i in range(4)]
    minutes = [_minute(i, max_dbfs=-15.0) for i in range(4)]
    html = build_report(
        summarize(events, quiet_hours=Config(tz="UTC").quiet_hours),
        config=Config(tz="UTC", threshold_dbfs=THRESHOLD),
        generated_at="2026-04-01 12:00 UTC",
        sensitivity_result=sensitivity(events, minutes, threshold_dbfs=THRESHOLD),
    )
    section = html.split(SECTION_HEADING, 1)[1].split("</table>", 1)[0]
    assert "<caption>" in section
    assert 'scope="col"' in section and 'scope="row"' in section
    assert SENSITIVITY_APPROXIMATION_NOTE in section


# --- canaries: the counters must be able to move -----------------------------------------


def test_the_counters_bite():
    """The assertions above are mostly about numbers *not* changing, which a scanner stuck
    at a constant would also satisfy. Show both counters responding to their input."""
    minutes = [_minute(0, max_dbfs=-10.0), _minute(1, max_dbfs=-50.0)]
    events = [_event(0, peak=-10.0), _event(600, peak=-34.0)]
    result = sensitivity(events, minutes, threshold_dbfs=THRESHOLD)

    assert _row(result, 0.0).events_at_or_above == 2
    assert _row(result, 3.0).events_at_or_above == 1, "the -34 dBFS event must drop at -32"
    assert _row(result, 0.0).loud_minutes == 1
    assert _row(result, -6.0).loud_minutes == 1
    assert _row(result, 6.0).loud_minutes == 1

    empty = sensitivity([], minutes, threshold_dbfs=THRESHOLD)
    assert _row(empty, 0.0).events_at_or_above == 0
    assert empty.headline_event_count == 0


def test_the_deltas_are_symmetric_and_include_the_configured_threshold():
    assert 0.0 in SENSITIVITY_DELTAS_DB
    assert sorted(SENSITIVITY_DELTAS_DB) == list(SENSITIVITY_DELTAS_DB)
    assert {-d for d in SENSITIVITY_DELTAS_DB} == set(SENSITIVITY_DELTAS_DB), (
        "asymmetric offsets would let the exhibit choose which direction to probe"
    )


def test_shipping_the_code_does_not_close_the_acoustics_review_gate():
    """`docs/ideation/04-impact-and-sequencing.md` puts EXP-03's *copy* behind a human
    gate: an acoustics SME reviews the wording so the approximation cannot be over-read.
    Building the section does not satisfy that, and the risk is that a shipped feature
    reads as a finished one and the row gets tidied away. Same shape, and the same reason,
    as `tests/test_doc_figures.py::test_rtf_08_is_still_recorded_as_open`.
    """
    from conftest import ROOT

    gates = (ROOT / "docs" / "ideation" / "04-impact-and-sequencing.md").read_text(encoding="utf-8")
    # The document mentions EXP-03 twice: once in the effort matrix, once in the
    # human-gate table. Only the second is the gate, so select on the reviewer column
    # rather than on the first line that happens to name the item.
    rows = [ln for ln in gates.splitlines() if "EXP-03" in ln and ln.lstrip().startswith("|")]
    assert rows, "docs/ideation/04-impact-and-sequencing.md no longer mentions EXP-03 at all"
    gate_rows = [ln for ln in rows if "Acoustics SME" in ln]
    assert gate_rows, (
        "the EXP-03 human-gate row is gone from docs/ideation/04-impact-and-sequencing.md's "
        "table, or no longer names its reviewer. The section shipped; the acoustics-SME "
        f"wording review did not. Rows found mentioning EXP-03: {rows}"
    )
