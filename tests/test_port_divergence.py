"""The Pi report and the browser report are two ports, and their differences are declared.

`spec/SEMANTICS.md` exists for exactly this: it lists the places `monitor/`+`report/`
(Python) and `pwa/` (JavaScript) deliberately do different things, so a divergence is a
decision somebody made rather than a thing that happened. Its detector half is held by
golden vectors both suites replay, and its cover half by `spec/report/cover.json`.

Its **report-structure** half was held by nothing, and had drifted twice:

1. `report/render.py` renders a ``Quiet-hours duration rollup`` -- the per-day accumulated
   duration table PR #117's own body calls "the exhibit an ordinance's per-day duration
   figure is actually read from". `pwa/report.js` has no such section and no per-day
   duration figure anywhere.
2. `monitor.config.QuietSchedule` holds a tuple of windows with **minute** granularity and
   a **per-weekday** ``days`` set. The browser's `summarize` takes ``startHour``/``endHour``
   and `pwa/index.html` offers two whole-hour inputs, so a Tuesdays-only rule, a 22:30
   start, or a second window in one day are configurations the Pi report answers and the
   browser cannot be asked about. Over the same events the two ports then disagree.

Neither was in the "Intentional Python ↔ PWA differences" list.

This module holds the report structure the way the vectors hold the detector: the sections
each port renders are compared against a declared map, so a section added to one port and
not the other fails until somebody writes down which it is. The map is a contract, not a
counter -- every resolution of a failure here is a correct one, because the only ways to
satisfy it are to port the section or to declare it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from report import render

ROOT = Path(__file__).resolve().parent.parent
BROWSER_REPORT = ROOT / "pwa" / "report.js"
BROWSER_APP = ROOT / "pwa" / "index.html"
PYTHON_REPORT = ROOT / "report" / "render.py"
SEMANTICS = ROOT / "spec" / "SEMANTICS.md"

#: Sections both ports render. Equivalent *content* under a different heading is not
#: shared -- the reader of one file and the reader of the other must find the same thing
#: under the same name, or the divergence is real and belongs below.
SHARED_SECTIONS = frozenset(
    {
        "What this can and cannot prove",
        "Windows erased by the operator",
        "Calendar heatmap",
        "Event types (coarse hint)",
        "Summary",
        "Quiet hours",
        "Methodology",
        "Limitations",
    }
)

#: Sections only the Pi report renders, each with the reason it is not in the browser.
#: A key here that the browser *does* render fails `test_every_declared_port_only_section...`,
#: so porting one and forgetting this file is not a quiet success.
PYTHON_ONLY_SECTIONS: dict[str, str] = {
    "Quiet-hours duration rollup": (
        "Not ported. It rests on the quiet-hours schedule model below: the table's fourth "
        "cell state exists only because a schedule can leave a weekday out, which the "
        "browser cannot express. Recorded in spec/SEMANTICS.md; the port is an owner call."
    ),
    "Measurement conditions": (
        "Session and calibration lineage are Pi-only, which spec/SEMANTICS.md already "
        "declares for the detector: the browser has no sessions table and no calibration "
        "offset, so it has no measurement conditions to state."
    ),
    "Ambient baseline": (
        "EXP-01's minute-level ambient ledger is written by the Pi monitor. The browser "
        "records no ambient minutes, so the section would have nothing behind it."
    ),
    "Threshold sensitivity": (
        "EXP-03 recomputes the event set at neighbouring thresholds from stored levels the "
        "browser does not keep."
    ),
    "Distributions": (
        "Named differently rather than absent: the browser splits the same content across "
        "'Events by hour of day' and 'Events by day'. Listed on both sides so the rename is "
        "the declared fact, not an accident of two lists."
    ),
    "Why there is deliberately no audio": (
        "The browser states the same rule in pwa/index.html, which is the page the operator "
        "reads before granting a microphone, rather than in the generated report."
    ),
}

#: Sections only the browser renders.
BROWSER_ONLY_SECTIONS: dict[str, str] = {
    "Monitoring gaps": (
        "The Pi report renders gaps inside its coverage and off-air prose rather than under "
        "a heading of their own."
    ),
    "Monitoring coverage": (
        "Same content, no heading on the Python side: report/violations.py's coverage "
        "sentence is replayed against both ports by spec/report/cover.json, so the claim is "
        "pinned even though the structure is not."
    ),
    "Events by hour of day": "The browser half of the 'Distributions' rename.",
    "Events by day": "The browser half of the 'Distributions' rename.",
}

_H2 = re.compile(r"<h2>(.*?)</h2>", re.DOTALL)
_PY_CONST = re.compile(r"^\{([A-Z_]+)\}$")
_JS_CONST = re.compile(r"^\$\{esc\(([A-Za-z_][A-Za-z0-9_]*)\)\}$")


def _python_sections() -> set[str]:
    """Every `<h2>` `report/render.py` can emit, with `{CONSTANT}` interpolations resolved."""
    found: set[str] = set()
    for raw in _H2.findall(PYTHON_REPORT.read_text(encoding="utf-8")):
        text = raw.strip()
        match = _PY_CONST.match(text)
        if match:
            value = getattr(render, match.group(1), None)
            assert isinstance(value, str), f"{match.group(1)} is not a string constant"
            found.add(value)
        else:
            assert "{" not in text, f"unresolved interpolation in a Python heading: {text!r}"
            found.add(text)
    return found


def _browser_sections() -> set[str]:
    """Every `<h2>` `pwa/report.js` can emit, with `${esc(CONST)}` resolved from the file."""
    source = BROWSER_REPORT.read_text(encoding="utf-8")
    constants = dict(re.findall(r'export const ([A-Z_]+) = "([^"]*)";', source))
    found: set[str] = set()
    for raw in _H2.findall(source):
        text = raw.strip()
        match = _JS_CONST.match(text)
        if match:
            assert match.group(1) in constants, f"{match.group(1)} is not a string constant"
            found.add(constants[match.group(1)])
        else:
            assert "${" not in text, f"unresolved interpolation in a browser heading: {text!r}"
            found.add(text)
    return found


def test_both_extractors_still_read_the_files_they_are_pointed_at() -> None:
    """The floor. An extractor that has stopped matching returns an empty set, and an empty
    set on both sides satisfies every comparison below -- a gate reading nothing looks
    exactly like two ports in perfect agreement."""
    python, browser = _python_sections(), _browser_sections()
    assert len(python) >= 8, f"only {len(python)} Python sections found; the extractor broke"
    assert len(browser) >= 8, f"only {len(browser)} browser sections found; the extractor broke"
    # Two headings that have been on both ports since before either list existed, one of
    # them resolved through a constant on each side.
    for heading in ("Summary", "Limitations", "What this can and cannot prove"):
        assert heading in python and heading in browser, heading


def test_the_two_report_ports_render_the_sections_the_declaration_says_they_do() -> None:
    """The whole point: a section in one port and not the other must be written down."""
    python, browser = _python_sections(), _browser_sections()
    declared_python = SHARED_SECTIONS | set(PYTHON_ONLY_SECTIONS)
    declared_browser = SHARED_SECTIONS | set(BROWSER_ONLY_SECTIONS)
    assert python == declared_python, (
        "report/render.py's sections and the declaration have drifted apart. "
        f"undeclared={sorted(python - declared_python)} "
        f"declared-but-absent={sorted(declared_python - python)}"
    )
    assert browser == declared_browser, (
        "pwa/report.js's sections and the declaration have drifted apart. "
        f"undeclared={sorted(browser - declared_browser)} "
        f"declared-but-absent={sorted(declared_browser - browser)}"
    )


@pytest.mark.parametrize("heading", sorted(PYTHON_ONLY_SECTIONS))
def test_every_declared_python_only_section_is_genuinely_absent_from_the_browser(
    heading: str,
) -> None:
    """Self-limiting, so the list cannot outlive the divergence it describes. Porting one of
    these and leaving it here fails, which is the direction an exemption list normally rots
    in silently."""
    assert heading not in _browser_sections(), (
        f"{heading!r} is declared Python-only and the browser renders it; delete the entry"
    )


@pytest.mark.parametrize("heading", sorted(BROWSER_ONLY_SECTIONS))
def test_every_declared_browser_only_section_is_genuinely_absent_from_python(
    heading: str,
) -> None:
    assert heading not in _python_sections(), (
        f"{heading!r} is declared browser-only and the Pi report renders it; delete the entry"
    )


def test_the_semantics_spec_names_every_port_only_report_section() -> None:
    """The declaration above is the executable half; `spec/SEMANTICS.md` is the half a reader
    finds. Neither is allowed to be the only one."""
    spec = SEMANTICS.read_text(encoding="utf-8")
    missing = [
        heading
        for heading in (*PYTHON_ONLY_SECTIONS, *BROWSER_ONLY_SECTIONS)
        if heading not in spec
    ]
    assert not missing, (
        "spec/SEMANTICS.md does not name these port-only report sections, so a reader of "
        f"the file written to list the divergences would not find them: {sorted(missing)}"
    )


def test_the_browser_cannot_be_asked_the_quiet_hours_question_the_pi_answers() -> None:
    """The divergence underneath the rollup one, and the one that changes a number.

    `QuietWindow` carries minute granularity and a per-weekday `days` set, and
    `QuietSchedule` holds a tuple of them. The browser takes one wrapping whole-hour pair.
    So for a Tuesdays-only rule, a 22:30 start, or two windows in a day, the two ports
    answer different questions over identical events -- and the browser has no input that
    could state the question at all.

    Pinned from both sides so that closing it in either fails here: give the browser a
    schedule, or take the schedule away from Python, and this test asks to be rewritten.
    """
    from monitor.config import QuietSchedule, QuietWindow

    window = QuietWindow(start_minute=22 * 60 + 30, end_minute=8 * 60, days=frozenset({1}))
    schedule = QuietSchedule(windows=(window,))
    assert schedule.windows[0].days == frozenset({1})
    assert window.start_minute % 60 != 0, "minute granularity is the half a whole hour cannot"

    browser = BROWSER_REPORT.read_text(encoding="utf-8")
    assert "startHour = 22, endHour = 8" in browser, (
        "pwa/report.js's summarize no longer takes a whole-hour pair; if it now takes a "
        "schedule, the divergence recorded in spec/SEMANTICS.md is closed and this test and "
        "that entry both need rewriting"
    )
    markup = BROWSER_APP.read_text(encoding="utf-8")
    assert 'id="startHour"' in markup and 'id="endHour"' in markup
    assert 'id="quietDays"' not in markup, (
        "pwa/index.html has gained a weekday control; the declared divergence is stale"
    )

    spec = SEMANTICS.read_text(encoding="utf-8")
    assert "per-weekday" in spec and "startHour" in spec, (
        "spec/SEMANTICS.md no longer states the quiet-hours schedule divergence"
    )
