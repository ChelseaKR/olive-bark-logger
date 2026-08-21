"""One-shot generator for spec/report/cover.json from the Python constants.

Kept in-tree so the shared vector is reproducible rather than hand-typed: run it after
an intentional wording change to the cover block, then review the diff. The gate
(`tests/test_export_caveats.py`) reads the committed JSON, so regenerating without
meaning to is caught the same way a detector vector edit is.
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

DOC = {
    "name": "report-cover",
    "description": (
        "Strings every human-readable export must carry, in both implementations. "
        "Python: report/render.py (cover_text_lines / cover_html) plus every writer in "
        "report/export.py and report/violations.py. Browser: pwa/report.js. Same rule as "
        "spec/detector/*.json - one list, replayed by tests/test_export_caveats.py and "
        "pwa/report.test.mjs, so the two ports cannot drift. See spec/SEMANTICS.md."
    ),
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
}


def main() -> int:
    out = Path(__file__).resolve().parent.parent / "spec" / "report" / "cover.json"
    out.write_text(json.dumps(DOC, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
