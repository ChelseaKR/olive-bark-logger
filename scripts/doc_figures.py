#!/usr/bin/env python3
"""Derive the figures the documents state about this repo, and write them.

`tests/test_doc_figures.py` already reads these numbers back from the tree and
fails the build when a document disagrees. What it never did was *produce* the
number: the gate says "§F says 10 waived CVEs; the Makefile has 12" and then a
person opens the file and retypes a digit.

That edit is mechanical, and it is charged to every branch that adds a test
file -- twice, because the validation-surface figure is stated in two
documents, and correcting one and not the other is itself a failure the gate
catches. Two branches that each add a test file therefore each have to edit the
same two lines, which is a merge conflict whose entire content is a number.

So the derivations live here, the gate imports them, and

    python3 scripts/doc_figures.py            # write the documents
    python3 scripts/doc_figures.py --check    # exit 1 if they are stale

is the whole edit. `make doc-figures` runs it. It is not a prerequisite of
`make verify`, for the same reason `snapshot` is not: a gate that repairs what
it checks cannot fail.

**Blockquotes are never rewritten.** This repository records a superseded claim
by quoting it verbatim next to the correction -- `docs/GAP-LEDGER.md` is built
that way, and `docs/DOCUMENTATION-AUDIT.md` opens with a correction that quotes
"33 Python/Node test files; 1 workflow file" on purpose. A writer that updated
those would erase the record it exists next to. `tests/test_doc_figures.py`
reads the documents with blockquotes stripped for exactly the same reason, so
the two halves agree about what counts as a claim.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

AUDITS = ROOT / "docs" / "RESPONSIBLE-TECH-AUDITS.md"
DOC_AUDIT = ROOT / "docs" / "DOCUMENTATION-AUDIT.md"
SCOPE = ROOT / "docs" / "PROJECT-SCOPE.md"
MAKEFILE = ROOT / "Makefile"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- the repo facts, read from the repo ----------------------------------------------


def waiver_count(root: Path = ROOT) -> int:
    """CVEs waived in `PIP_AUDIT_WAIVERS`, counted from the Makefile."""
    return len(re.findall(r"--ignore-vuln\s+\S+", _text(root / "Makefile")))


def adr_count(root: Path = ROOT) -> int:
    return len(list((root / "docs" / "adr").glob("*.md")))


def count_test_files(root: Path = ROOT) -> int:
    """Python and Node test files, the two suites `make verify` runs."""
    return len(list((root / "tests").glob("test_*.py"))) + len(
        list((root / "pwa").glob("*.test.mjs"))
    )


def workflow_count(root: Path = ROOT) -> int:
    return len(list((root / ".github" / "workflows").glob("*.yml")))


# --- writing them back ---------------------------------------------------------------

WAIVERS = re.compile(r"(?<=\*\*)\d+(?=\*\* dev-toolchain-only CVEs are waived)")
ADRS = re.compile(r"(?<=\|)(?P<space>\s*)\d+(?= ADRs;)")
SURFACE = re.compile(
    r"(?P<tests>\d+) Python/Node test files(?P<between>[;,] (?:and )?)(?P<flows>\d+) workflow files?"
)


def _outside_blockquotes(text: str, replace) -> str:
    """`replace` applied to every line that is not a blockquote."""
    return "\n".join(
        line if line.lstrip().startswith(">") else replace(line) for line in text.split("\n")
    )


def rewrite(path: Path, root: Path = ROOT) -> str:
    """`path`'s text with every figure it states set to the derived value."""
    text = _text(path)
    if path.name == AUDITS.name:
        waivers = str(waiver_count(root))
        return _outside_blockquotes(text, lambda line: WAIVERS.sub(waivers, line))
    if path.name in (DOC_AUDIT.name, SCOPE.name):
        tests, flows = count_test_files(root), workflow_count(root)
        plural = "" if flows == 1 else "s"

        def surface(line: str) -> str:
            line = SURFACE.sub(
                lambda m: (
                    f"{tests} Python/Node test files{m.group('between')}"
                    f"{flows} workflow file{plural}"
                ),
                line,
            )
            if path.name == DOC_AUDIT.name:
                line = ADRS.sub(lambda m: f"{m.group('space')}{adr_count(root)}", line)
            return line

        return _outside_blockquotes(text, surface)
    raise AssertionError(f"no figures are derived for {path.name}")  # pragma: no cover


DOCUMENTS = (AUDITS, DOC_AUDIT, SCOPE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="report stale documents and exit 1 without writing"
    )
    arguments = parser.parse_args(argv)

    stale: list[str] = []
    for path in DOCUMENTS:
        before = _text(path)
        after = rewrite(path)
        if before == after:
            continue
        stale.append(path.relative_to(ROOT).as_posix())
        if not arguments.check:
            path.write_text(after, encoding="utf-8")

    if not stale:
        print(
            f"doc figures: already current -- {waiver_count()} waived CVEs, "
            f"{adr_count()} ADRs, {count_test_files()} test files, "
            f"{workflow_count()} workflow files"
        )
        return 0
    if arguments.check:
        print(
            "doc figures: stale in " + ", ".join(stale) + " -- run `make doc-figures`",
            file=sys.stderr,
        )
        return 1
    print("doc figures: rewrote " + ", ".join(stale))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
