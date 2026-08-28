"""Generate spec/report/cover.json from the Python constants that render the strings.

Kept in-tree so the shared vector is reproducible rather than hand-typed. Every string
below is *imported* from the module that puts it in front of a person, so the JSON cannot
say one thing while the report says another; only the two `_`-prefixed annotations are
prose local to the vector, because nothing renders them.

The generator is itself gated. `tests/test_export_caveats.py` compares `render()` against
the committed `spec/report/cover.json` and fails on any difference, so a wording change
that skips the vector is caught, and so is a hand-edit to the vector that no constant
backs. That gate only reads: regenerating stays a deliberate act, run after an intentional
wording change and reviewed as a diff, exactly like a detector vector.

    .venv/bin/python scripts/gen_cover_spec.py
"""

from __future__ import annotations

import json
from pathlib import Path

from report.render import (
    COVER_CAN,
    COVER_CANNOT,
    COVER_PRIVACY,
    NO_VERDICT_NOTE,
    UNCALIBRATED_HEADLINE,
)
from report.violations import (
    ABSENCE_NOTE,
    COVERAGE_HEADING,
    COVERAGE_SENTENCE_TEMPLATE,
    COVERAGE_UNKNOWN_NOTE,
)

SPEC_PATH = Path(__file__).resolve().parent.parent / "spec" / "report" / "cover.json"

DESCRIPTION = (
    "Strings every human-readable export must carry, in both implementations. Python: "
    "report/render.py (cover_text_lines / cover_html) plus every writer in report/export.py "
    "and report/violations.py; the coverage block is report/violations.py. Browser: "
    "pwa/report.js. Same rule as spec/detector/*.json - one list, replayed by "
    "tests/test_export_caveats.py and pwa/report.test.mjs, so the two ports cannot drift. See "
    "spec/SEMANTICS.md."
)

# Spec-only prose: these two keys document the vector for whoever reads it next. They are
# `_`-prefixed because no export renders them, so unlike every other string here they have
# no constant to be imported from.
COVERAGE_WHY = (
    "A quiet-hours count is only readable against the time it was counted over. An outage "
    "during quiet hours removes events, so a monitor that dropped out for most of the night "
    "produces a low count that reads as a quiet night. Python carried this from issue #39; the "
    "browser edition made the same 'honest submission' claim with no coverage figure at all "
    "until issue #64. These strings are what both ports must say, verbatim."
)

SENTENCE_TEMPLATE_NOTE = (
    "{monitored}, {wall} and {unmonitored} are hours to one decimal place; {pct} is a "
    "whole-number percentage. Both ports format the numbers themselves and must produce this "
    "sentence exactly. Python appends a further sentence naming the recorded span; the browser "
    "does not, so the shared claim is the prefix."
)

DOC = {
    "name": "report-cover",
    "description": DESCRIPTION,
    "cover": {
        "heading": "What this can and cannot prove",
        "can_label": "What it can show:",
        "cannot_label": "What it cannot prove:",
        "can": list(COVER_CAN),
        "cannot": list(COVER_CANNOT),
        "privacy": COVER_PRIVACY,
    },
    "no_verdict": NO_VERDICT_NOTE,
    "uncalibrated_headline": UNCALIBRATED_HEADLINE,
    "coverage": {
        "_why": COVERAGE_WHY,
        "heading": COVERAGE_HEADING,
        "absence_note": ABSENCE_NOTE,
        "unknown_note": COVERAGE_UNKNOWN_NOTE,
        "sentence_template": COVERAGE_SENTENCE_TEMPLATE,
        "_sentence_template_note": SENTENCE_TEMPLATE_NOTE,
    },
}


def render() -> str:
    """The exact bytes the committed vector must contain."""
    return json.dumps(DOC, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    SPEC_PATH.write_text(render(), encoding="utf-8")
    print(f"Wrote {SPEC_PATH}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
