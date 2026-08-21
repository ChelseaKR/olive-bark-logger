"""Merge-blocking: no document may describe a gap the code has already closed.

`docs/GAP-LEDGER.md` and the README's Standards Conformance table are this repository's
statement of what is not done yet, and the README's own framing makes them load-bearing:
"treat the audit file as the point-in-time evidence trail, this table as the current
claim." Three of those claims described work that had already landed -- `--log-format
json` shipped 2026-07-14 and was still called "not implemented yet" two and a half weeks
later; the PWA axe scan landed six days after the entry saying it never ran, and stayed
stale for a month.

Under-claiming is the gentler failure, but it is the same defect: a document about the
code that stopped tracking the code. A ledger no test can read will drift again.

Each check below pairs a **code fact** (does this capability exist, verified against the
source, not against another document) with the phrases no document may carry while it
does. The assertion is the absence of the stale claim, and it only fires when the
capability is genuinely present -- so removing the feature relaxes the check rather than
breaking it, and the ledger is allowed to describe a gap that is real.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import ROOT

DOCS = {
    "README.md": ROOT / "README.md",
    "docs/GAP-LEDGER.md": ROOT / "docs" / "GAP-LEDGER.md",
    "docs/a11y/STATEMENT.md": ROOT / "docs" / "a11y" / "STATEMENT.md",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _docs_saying(phrase: str) -> list[str]:
    """Which documents carry this phrase (case-insensitive)."""
    return [name for name, path in DOCS.items() if phrase.lower() in _text(path).lower()]


# --- code facts -------------------------------------------------------------------


def json_log_format_is_implemented() -> bool:
    """GAP-OBS-1: `--log-format json` emits newline-delimited JSON operator lines."""
    log_module = ROOT / "monitor" / "log.py"
    if not log_module.exists():
        return False
    source = _text(log_module)
    if "def emit(" not in source or "json.dumps" not in source:
        return False
    config = _text(ROOT / "monitor" / "config.py")
    cli_has_flag = "--log-format" in _text(ROOT / "monitor" / "service.py")
    return "log_format" in config and cli_has_flag


def pwa_page_is_scanned_by_axe() -> bool:
    """GAP-A11Y-1: CI runs an axe pass over the PWA page itself, not only its logic."""
    ci = _text(ROOT / ".github" / "workflows" / "ci.yml")
    return bool(re.search(r"pa11y[^\n]*--runner axe[\s\S]{0,200}?pwa/index\.html", ci))


# --- the gate ---------------------------------------------------------------------


def test_json_log_format_is_actually_implemented():
    """The premise of the check below. If this fails the ledger is right and the code
    regressed -- which is a different bug, and this file must not hide it."""
    assert json_log_format_is_implemented(), (
        "`--log-format json` is no longer implemented. Do not relax the check below to "
        "match; restore the feature or reopen GAP-OBS-1 as a real gap."
    )


def test_no_document_calls_json_log_format_unbuilt():
    stale = [
        "`--log-format json` is\nnot implemented yet",
        "--log-format json` opt-in **planned**",
        "log-format json` is not implemented",
    ]
    offenders = {phrase: _docs_saying(phrase) for phrase in stale}
    offenders = {p: docs for p, docs in offenders.items() if docs}
    assert not offenders, f"documents still call a shipped feature unbuilt: {offenders}"
    # Broader net: "not implemented yet" and "planned" must not sit next to the flag.
    for name, path in DOCS.items():
        for line in _text(path).splitlines():
            if "--log-format json" not in line:
                continue
            lowered = line.lower()
            assert "not implemented" not in lowered, f"{name}: {line.strip()}"
            assert "planned" not in lowered, f"{name}: {line.strip()}"


def test_pwa_page_is_actually_scanned_by_axe():
    """Premise of the check below, asserted against ci.yml rather than assumed."""
    assert pwa_page_is_scanned_by_axe(), (
        "CI no longer runs an axe pass over pwa/index.html. Do not relax the check "
        "below to match; restore the step or reopen that half of GAP-A11Y-1."
    )


def test_no_document_says_the_pwa_page_is_never_scanned():
    stale = [
        "`pwa/index.html` is never scanned",
        "is not scanned by axe/pa11y",
        "PWA surface unscanned",
        "never been scanned by axe/pa11y",
    ]
    offenders = {phrase: docs for phrase in stale if (docs := _docs_saying(phrase))}
    assert not offenders, (
        "documents still say the PWA page is unscanned while CI scans it on every push "
        f"and PR: {offenders}"
    )


def test_the_manual_pwa_pass_is_still_described_as_open():
    """The other direction: correcting the axe clause must not quietly upgrade the whole
    entry. An automated scan is not a human walkthrough, and the ledger must still say
    the walkthrough has not happened."""
    ledger = _text(DOCS["docs/GAP-LEDGER.md"])
    entry = ledger.split("## GAP-A11Y-1")[1].split("## GAP-REL-1")[0]
    assert "Lighthouse" in entry
    assert "ACR/VPAT" in entry or "ACR" in entry
    assert "stale" in entry.lower()
    assert "manual pass" in entry.lower() or "walkthrough" in entry.lower()
    assert "VoiceOver" in entry or "NVDA" in entry

    statement = _text(DOCS["docs/a11y/STATEMENT.md"])
    assert "never been walked" in statement or "no manual" in statement.lower()
    assert "Partially conforms" in statement


def test_the_scanner_bites_on_a_planted_stale_claim(tmp_path, monkeypatch):
    """Canary: prove `_docs_saying` finds a stale phrase rather than silently missing it,
    on the same helper the checks above use."""
    planted = tmp_path / "PLANTED.md"
    planted.write_text(
        "Opt-in `--log-format json` is not implemented yet.\n"
        "`pwa/index.html` is never scanned by pa11y/axe.\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(DOCS, "PLANTED.md", planted)
    assert _docs_saying("`pwa/index.html` is never scanned") == ["PLANTED.md"]
    assert _docs_saying("log-format json` is not implemented") == ["PLANTED.md"]


def test_the_ledger_points_at_the_test_that_reads_it():
    """A ledger no test can read will drift again; say where the reader is."""
    assert "tests/test_gap_ledger.py" in _text(DOCS["docs/GAP-LEDGER.md"])
