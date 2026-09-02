"""Merge-blocking: no export path ships without its caveats, in either implementation.

`report/violations.py` says the cover block is written into the CSV "so the caveat travels
with the file". It travelled with one CSV. The event CSV had none, and the whole browser
edition -- the zero-hardware route, no Raspberry Pi and no command line, the path with the
lowest barrier to reaching for it -- had none at all: `pwa/report.js` exported a bare table
of timestamps and
`within_quiet_hours,yes` with nothing attached saying what that does and does not mean.

Two gates, and the second is the one that matters:

1. **Content.** Every export path's output carries every string in
   `spec/report/cover.json` -- the single shared list both implementations are held to,
   the same arrangement `spec/detector/*.json` uses to stop the two detectors drifting.
2. **Enumeration.** Export paths are *discovered* from the source, not listed by hand,
   and the discovered set must equal the set this file actually renders and checks. A new
   export path fails the gate until it is exercised here, so it cannot ship unchecked.
   The failure mode this avoids is the one that let the browser CSV drift: a gate that
   checks the paths someone remembered to name.

**Discovery is by behaviour, not only by name (2026-08-29).** The enumeration gate above
described itself as behaviour-proof and was not: it discovered Python export paths purely
from a name pattern (`*_to_csv`, `build_report`, `build_*_html`), and `render_status` in
`report/status.py` matched none of them. `status.html` is an artifact a person is handed
-- the README tells the operator to open it from disk -- it printed two quiet-hours counts,
and it shipped with neither the cover block nor the no-verdict line for as long as it
existed. The gate's own docstring named this exact failure mode while the gate had it.

So an export path is now identified by what its body *builds*, which is what actually
makes something an artifact:

* it emits a complete HTML document (a `<!DOCTYPE html` literal in its own body), or
* it writes a CSV file (a `csv.writer(...)` call in its own body),

and the name pattern is kept as a union member so discovery can only ever widen. A helper
that returns an HTML *fragment* (`coverage_html`, `cover_html`) builds no document and is
not an export path; a function that re-encodes an already-built artifact
(`report/pdf_export.py`'s `write_tagged_pdf`, which is handed finished HTML) carries the
caveats through from its input rather than emitting them, so it is not a producer either.

Canaries prove both scanners bite, on the pattern `tests/gates.py` uses -- the same
function that clears the tree is the one shown to flag a planted violation.
"""

from __future__ import annotations

import ast
import csv
import json
import re
from datetime import datetime, timezone

from monitor.config import Config, QuietHours
from monitor.detector import Event
from report.aggregate import summarize
from report.export import events_to_csv
from report.render import (
    COVER_CAN,
    COVER_CANNOT,
    COVER_PRIVACY,
    NO_VERDICT_NOTE,
    UNCALIBRATED_HEADLINE,
    build_report,
    cover_text_lines,
)
from report.status import StatusAggregates, render_status
from report.violations import build_violation_report_html, compute_violations, violations_to_csv

from conftest import ROOT

SPEC = json.loads((ROOT / "spec" / "report" / "cover.json").read_text(encoding="utf-8"))
COVER = SPEC["cover"]

# Every string that must appear, verbatim, in every human-readable export.
REQUIRED_IN_EVERY_EXPORT = [COVER["heading"], *COVER["can"], *COVER["cannot"], COVER["privacy"]]

# The one helper pair an export path must reach to emit the cover block.
COVER_HELPERS = {"cover_text_lines", "cover_html"}

# A Python export path: a public function in report/ that produces an artifact a person is
# handed. Two independent signatures, unioned, so a path has to evade both to ship
# unchecked:
#
#  * NAME -- the original pattern, kept verbatim. It is only ever added to.
#  * BEHAVIOUR -- the function's own body builds a whole HTML document or writes a CSV.
#    Name-only discovery is what let `render_status` ship uncovered; a new export path
#    can be called anything, but it cannot produce an artifact without building one.
PY_EXPORT_PATTERN = re.compile(r"^(?!_)(.*_to_csv|build_report|build_.*_html)$")

# The behavioural half. `<!DOCTYPE html` marks a complete document (a fragment helper such
# as `cover_html` has none); `csv.writer` marks a CSV file being written.
HTML_DOCUMENT_MARKER = re.compile(r"<!doctype html", re.IGNORECASE)

# The browser twin. Same union: the name alternation is widened (strictly -- every name
# the old pattern matched still matches), plus the same `<!DOCTYPE html` behaviour test.
JS_EXPORT_PATTERN = re.compile(r"^(.*[Cc]sv|(build|render).*Html)$")

# The paths this file renders and asserts on below. Discovery must land on exactly these.
PY_CHECKED = {
    "events_to_csv",
    "violations_to_csv",
    "build_report",
    "build_violation_report_html",
    "render_status",
}
JS_CHECKED = {"eventsToCsv", "violationsToCsv", "buildReportHtml"}


def _events():
    base = datetime(2026, 1, 1, 23, tzinfo=timezone.utc).timestamp()
    return [
        Event(base, base + 4.0, 4.0, -8.0, -12.0, coarse_tag="bark-like"),
        Event(base + 3600 * 13, base + 3600 * 13 + 1.5, 1.5, -20.0, -24.0),
    ]


# --- scanners (shared by the gates and their canaries) -------------------------------


def _builds_an_html_document(node: ast.FunctionDef) -> bool:
    """This function's own body contains a whole-HTML-document string literal.

    Nested functions are walked with it, which is correct: a closure that assembles the
    document is still this path building it.
    """
    return any(
        isinstance(sub, ast.Constant)
        and isinstance(sub.value, str)
        and HTML_DOCUMENT_MARKER.search(sub.value)
        for sub in ast.walk(node)
    )


def _writes_a_csv(node: ast.FunctionDef) -> bool:
    """This function's own body calls `csv.writer(...)`, i.e. it writes a CSV file."""
    return any(
        isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Attribute)
        and sub.func.attr == "writer"
        for sub in ast.walk(node)
    )


def _is_python_export(node: ast.FunctionDef) -> bool:
    """A public function in report/ that hands a person a finished artifact.

    Name OR behaviour: either signature alone is enough, so widening one never narrows
    the set. Private helpers (`_`-prefixed) are excluded from the behavioural half the
    same way the name pattern excludes them.
    """
    if PY_EXPORT_PATTERN.match(node.name):
        return True
    if node.name.startswith("_"):
        return False
    return _builds_an_html_document(node) or _writes_a_csv(node)


def discover_python_exports(source: str) -> set[str]:
    """Public artifact-producing functions defined in a Python report module."""
    return {
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and _is_python_export(node)
    }


def _is_js_export(name: str, body: str) -> bool:
    """The browser twin of `_is_python_export`: name OR whole-document behaviour."""
    return bool(JS_EXPORT_PATTERN.match(name)) or bool(HTML_DOCUMENT_MARKER.search(body))


def discover_js_exports(source: str) -> set[str]:
    """Exported artifact-producing functions in a PWA report module."""
    return {
        m.group(1)
        for m in re.finditer(r"^export function (\w+)[\s\S]*?\n}\n", source, re.MULTILINE)
        if _is_js_export(m.group(1), m.group(0))
    }


def uncovered_python_exports(source: str) -> list[str]:
    """Export paths in this source whose body never reaches a cover helper."""
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.FunctionDef) and _is_python_export(node)):
            continue
        called = {
            sub.func.id
            for sub in ast.walk(node)
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
        }
        if not called & COVER_HELPERS:
            offenders.append(node.name)
    return offenders


def uncovered_js_exports(source: str) -> list[str]:
    """Browser export paths whose body never reaches the shared preamble/cover helper."""
    offenders: list[str] = []
    for match in re.finditer(r"^export function (\w+)[\s\S]*?\n}\n", source, re.MULTILINE):
        name, body = match.group(1), match.group(0)
        if not _is_js_export(name, body):
            continue
        if "csvPreamble(" not in body and "coverHtml(" not in body:
            offenders.append(name)
    return offenders


# --- the shared list is the same list on both sides ---------------------------------


def test_python_cover_constants_match_the_shared_spec():
    """The vector is not a second copy of the strings -- it is *the* copy, and the Python
    constants are checked against it. Changing the wording means changing the vector on
    purpose (`scripts/gen_cover_spec.py`), exactly like a detector vector."""
    assert list(COVER_CAN) == COVER["can"]
    assert list(COVER_CANNOT) == COVER["cannot"]
    assert COVER["privacy"] == COVER_PRIVACY
    assert SPEC["no_verdict"] == NO_VERDICT_NOTE
    assert SPEC["uncalibrated_headline"] == UNCALIBRATED_HEADLINE
    assert COVER["heading"] in "\n".join(cover_text_lines())


def test_browser_cover_constants_match_the_shared_spec():
    """The JS port is held to the same vector. Read from source so this holds without a
    Node runtime; `pwa/report.test.mjs` replays it against the live module too."""
    js = (ROOT / "pwa" / "report.js").read_text(encoding="utf-8")
    # Source wraps long strings with `+` concatenation; join the pieces back before match.
    flattened = re.sub(r'"\s*\+\s*\n?\s*"', "", js)
    required = [*COVER["can"], *COVER["cannot"], COVER["privacy"], SPEC["no_verdict"]]
    missing = [s for s in required if s not in flattened]
    assert not missing, f"pwa/report.js is missing shared strings: {[s[:60] for s in missing]}"
    assert SPEC["uncalibrated_headline"] in flattened
    assert COVER["heading"] in flattened


# --- 1. content: every export path's output carries the caveats ----------------------


def _rendered_python_exports(tmp_path) -> dict[str, str]:
    """Every artifact the Python side can hand to someone, rendered."""
    config = Config(tz="UTC")
    events = _events()
    summary = summarize(events, quiet_hours=config.quiet_hours, tz=timezone.utc)
    report = compute_violations(events, quiet_hours=QuietHours(22, 8), tz=timezone.utc)

    events_csv = tmp_path / "events.csv"
    events_to_csv(events, events_csv)
    violations_csv = tmp_path / "violations.csv"
    violations_to_csv(events, violations_csv, quiet_hours=QuietHours(22, 8), tz=timezone.utc)

    return {
        "build_report": build_report(summary, config=config, generated_at="2026-01-01 00:00 UTC"),
        "build_violation_report_html": build_violation_report_html(
            report,
            threshold_dbfs=-35.0,
            min_duration_s=0.4,
            generated_at="2026-01-01 00:00 UTC",
            calibrated=False,
        ),
        "events_to_csv": events_csv.read_text(encoding="utf-8"),
        "violations_to_csv": violations_csv.read_text(encoding="utf-8"),
        # The local status page (README "Local status page"): a file the operator is
        # told to double-click open, printing quiet-hours counts. It is an export path.
        "render_status": render_status(
            {"updated_at": events[0].start, "status": "ok"},
            StatusAggregates(
                summary=summary,
                quiet_window=config.quiet_hours.label(),
                tz_name="UTC",
            ),
            now=events[0].start,
        ),
    }


def test_every_python_export_carries_the_cover(tmp_path):
    missing: dict[str, list[str]] = {}
    for name, text in _rendered_python_exports(tmp_path).items():
        absent = [s for s in REQUIRED_IN_EVERY_EXPORT if s not in text]
        if absent:
            missing[name] = [s[:60] for s in absent]
    assert not missing, f"export paths shipping without the cover block: {missing}"


def test_quiet_hours_counts_never_appear_without_a_no_verdict_statement(tmp_path):
    """Anything reporting a quiet-hours count says the count is not a finding -- either as
    the no-verdict line or as the cover's third `cannot` bullet, which says the same."""
    for name, text in _rendered_python_exports(tmp_path).items():
        if "quiet hours" not in text.lower():
            continue
        assert NO_VERDICT_NOTE in text or COVER["cannot"][2] in text, (
            f"{name}: reports a quiet-hours count with no no-verdict statement"
        )


def test_csv_exports_keep_their_data_rows_machine_readable(tmp_path):
    """The cover is a comment preamble, not a mangled header: the data below it parses."""
    events_csv = tmp_path / "events.csv"
    events_to_csv(_events(), events_csv)
    lines = events_csv.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# ")
    rows = list(csv.reader([ln for ln in lines if not ln.startswith("#")]))
    assert rows[0][0] == "start_unix"
    assert len(rows) == 3  # header + 2 events


# --- 2. enumeration: a new export path cannot ship unchecked -------------------------


def test_discovered_python_export_paths_are_exactly_the_checked_ones():
    found: set[str] = set()
    for path in sorted((ROOT / "report").glob("*.py")):
        found |= discover_python_exports(path.read_text(encoding="utf-8"))
    assert found == PY_CHECKED, (
        "Python export paths changed. Every artifact a person is handed must be rendered "
        "and asserted on in this file before it can ship: "
        f"unchecked={sorted(found - PY_CHECKED)}, gone={sorted(PY_CHECKED - found)}"
    )


def test_discovered_browser_export_paths_are_exactly_the_checked_ones():
    found = discover_js_exports((ROOT / "pwa" / "report.js").read_text(encoding="utf-8"))
    assert found == JS_CHECKED, (
        "Browser export paths changed. Add the new one to `pwa/report.test.mjs`'s checked "
        f"set too: unchecked={sorted(found - JS_CHECKED)}, gone={sorted(JS_CHECKED - found)}"
    )


def test_every_python_export_path_goes_through_the_shared_cover_helper():
    """Static twin of the content gate: each export path's own body must reach the one
    cover helper. Content assertions catch a path that forgot; this catches a path that
    reimplements the block and can then drift from the shared spec."""
    offenders: dict[str, list[str]] = {}
    for path in sorted((ROOT / "report").glob("*.py")):
        found = uncovered_python_exports(path.read_text(encoding="utf-8"))
        if found:
            offenders[path.name] = found
    assert not offenders, f"export paths that never emit the cover block: {offenders}"


def test_every_browser_export_path_goes_through_the_shared_cover_helper():
    offenders = uncovered_js_exports((ROOT / "pwa" / "report.js").read_text(encoding="utf-8"))
    assert not offenders, f"browser export paths that never emit the cover block: {offenders}"


def test_the_readme_enumerates_every_artifact_it_claims_the_cover_leads():
    """The README's Guardrails bullet says the cover "leads every artifact" and then
    enumerates them by hand. It listed four while five existed, for as long as the fifth
    existed. Tie the sentence to discovery: while `render_status` is a discovered export
    path, that bullet has to name the page it produces."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    bullet = readme.split("**The caveats travel with every export.**")[1].split("\n\n")[0]
    # The *enumeration* only: the span between "produces" and the dash that closes the
    # list. Checking the whole bullet would let prose about the status page elsewhere in
    # the paragraph satisfy a list that does not mention it -- which it did, first try.
    enumeration = bullet.split("produces")[1].split("—")[1]
    assert "render_status" in PY_CHECKED, (
        "premise: the status page is a checked export path. If it stopped being one, fix "
        "that rather than relaxing the README check below."
    )
    assert "status page" in enumeration.lower(), (
        "README's 'every artifact' list does not name the local status page, which is one "
        f"of them: {enumeration.strip()!r}"
    )


def test_pwa_test_file_exercises_the_same_export_paths():
    """The browser suite is the runtime half of this gate; keep the two sets in step so a
    path checked here is not silently unchecked there."""
    js_test = (ROOT / "pwa" / "report.test.mjs").read_text(encoding="utf-8")
    for name in sorted(JS_CHECKED):
        assert name in js_test, f"pwa/report.test.mjs does not exercise {name}"
    assert "cover.json" in js_test, "pwa/report.test.mjs must replay the shared spec vector"


# --- canaries: prove the scanners bite ----------------------------------------------


def test_export_discovery_flags_a_planted_path():
    planted_py = "def summary_to_csv(events, path):\n    return 0\n"
    assert discover_python_exports(planted_py) - PY_CHECKED == {"summary_to_csv"}
    planted_js = "export function summaryToCsv(records) {\n  return '';\n}\n"
    assert discover_js_exports(planted_js) - JS_CHECKED == {"summaryToCsv"}


def test_export_discovery_flags_a_path_whose_name_matches_nothing():
    """The regression canary for the hole this gate actually had.

    `render_status` built a whole `status.html`, printed quiet-hours counts, and was
    invisible to name-only discovery. Both plants below are named so that
    `PY_EXPORT_PATTERN` / the JS name pattern reject them; behaviour has to find them.
    """
    named_py = "def paint_the_dashboard(data):\n    return '<!DOCTYPE html>\\n<html></html>'\n"
    assert not PY_EXPORT_PATTERN.match("paint_the_dashboard"), "plant must evade the name half"
    assert discover_python_exports(named_py) == {"paint_the_dashboard"}

    writes_csv = "def dump(rows, path):\n    w = csv.writer(path)\n    w.writerow(rows)\n"
    assert not PY_EXPORT_PATTERN.match("dump"), "plant must evade the name half"
    assert discover_python_exports(writes_csv) == {"dump"}

    named_js = "export function paintDashboard(d) {\n  return `<!DOCTYPE html>`;\n}\n"
    assert not JS_EXPORT_PATTERN.match("paintDashboard"), "plant must evade the name half"
    assert discover_js_exports(named_js) == {"paintDashboard"}


def test_export_discovery_ignores_fragment_helpers_and_private_functions():
    """The other half of the canary: behaviour must not flag everything that touches
    HTML, or the gate becomes noise someone widens `PY_CHECKED` to silence."""
    fragment = "def sidebar_html(x):\n    return '<section>' + x + '</section>'\n"
    assert discover_python_exports(fragment) == set()
    private = "def _paint(data):\n    return '<!DOCTYPE html>'\n"
    assert discover_python_exports(private) == set()


def test_the_name_half_of_discovery_is_never_narrowed():
    """`PY_EXPORT_PATTERN` and the JS pattern are a floor, not a knob. Every name the
    gate was written to catch still matches, so a future edit can only widen."""
    for name in (
        "events_to_csv",
        "violations_to_csv",
        "build_report",
        "build_violation_report_html",
    ):
        assert PY_EXPORT_PATTERN.match(name), f"name half narrowed: {name} no longer matches"
    for name in ("eventsToCsv", "violationsToCsv", "buildReportHtml"):
        assert JS_EXPORT_PATTERN.match(name), f"JS name half narrowed: {name} no longer matches"


def test_cover_scanner_flags_a_planted_uncovered_export():
    planted_py = "def notes_to_csv(events, path):\n    return 1\n"
    assert uncovered_python_exports(planted_py) == ["notes_to_csv"], (
        "cover scanner failed to flag a planted export with no cover block -- gate is dead"
    )
    planted_js = "export function notesToCsv(records) {\n  return 'a,b';\n}\n"
    assert uncovered_js_exports(planted_js) == ["notesToCsv"]


def test_cover_scanner_passes_an_export_that_does_emit_the_cover():
    """The other half of a canary: it must not flag a compliant path, or it is noise."""
    ok_py = "def notes_to_csv(events, path):\n    lines = cover_text_lines()\n    return 1\n"
    assert uncovered_python_exports(ok_py) == []
    ok_js = "export function notesToCsv(records) {\n  return csvPreamble();\n}\n"
    assert uncovered_js_exports(ok_js) == []
