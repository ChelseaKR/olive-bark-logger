"""The branch-ruleset check must be able to see the live configuration, or say it cannot.

The check this replaces could not fail:

    gh api repos/ChelseaKR/olive-bark-logger/rulesets --jq '.[] | select(.name=="main")'

The live ruleset is named `protect-main`, so it printed nothing and exited 0 forever, and
two documents in this repo concluded from that silence that no ruleset had been applied
-- while a third was engineered around the fact that one was.

Everything here is offline: the diff logic runs against a recorded copy of the live
ruleset (`--live-json`), so the assertions hold in CI without network or a `gh` token.
The gate is written as the absence of the overstatement -- there is no input on which
this check reports a pass without having read a live configuration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

from check_ruleset import (
    CANNOT_VERIFY,
    CannotVerify,
    diff_ruleset,
    fetch_live_ruleset,
)
from check_ruleset import main as check_main

COMMITTED = json.loads((ROOT / ".github" / "rulesets" / "main.json").read_text(encoding="utf-8"))

# The live ruleset as returned by the API on 2026-08-15, trimmed to the fields the check
# reads. Recorded rather than fetched so this test is offline and deterministic; the
# live-vs-file question is answered by `make ruleset-check`, not by the test suite.
LIVE_2026_08_15 = {
    "id": 18752850,
    "name": "protect-main",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/main"]}},
    "rules": [
        {"type": "non_fast_forward"},
        {"type": "deletion"},
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": False,
                "do_not_enforce_on_create": False,
                "required_status_checks": [
                    {"context": "verify"},
                    *(
                        {"context": f"test-matrix ({os_}, {py})"}
                        for os_ in ("ubuntu-latest", "macos-latest")
                        for py in ("3.9", "3.10", "3.11", "3.12", "3.13")
                    ),
                ],
            },
        },
    ],
    "bypass_actors": [{"actor_id": 3114598, "actor_type": "User", "bypass_mode": "pull_request"}],
}


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "live.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_the_check_sees_the_live_ruleset_despite_the_different_name(tmp_path, capsys):
    """The whole defect: selecting by name found nothing and read as 'not applied'."""
    rc = check_main(["--live-json", str(_write(tmp_path, LIVE_2026_08_15))])
    out = capsys.readouterr().out
    assert rc == 1
    assert "protect-main" in out, "the check must name the live ruleset it found"
    assert "DIFFERS" in out


def test_every_documented_difference_is_reported():
    """The four the issue enumerated, plus the name. Each named, not just counted."""
    differences = "\n".join(diff_ruleset(COMMITTED, LIVE_2026_08_15))
    assert "name" in differences and "protect-main" in differences
    assert "required_signatures" in differences
    assert "pull_request" in differences
    assert "strict_required_status_checks_policy" in differences
    assert "bypass_actors" in differences


def test_a_matching_ruleset_is_reported_as_a_match(tmp_path, capsys):
    """The other half of a real check: it must be able to pass, or it is noise."""
    rc = check_main(["--live-json", str(_write(tmp_path, COMMITTED))])
    assert rc == 0
    assert "matches" in capsys.readouterr().out


def test_a_weakened_ruleset_never_passes(tmp_path):
    """Each weakening on its own is caught -- not only the full set together."""
    for weakened in (
        {**COMMITTED, "enforcement": "disabled"},
        {
            **COMMITTED,
            "bypass_actors": [{"actor_id": 1, "actor_type": "User", "bypass_mode": "always"}],
        },
        {
            **COMMITTED,
            "rules": [r for r in COMMITTED["rules"] if r["type"] != "required_signatures"],
        },
        {**COMMITTED, "rules": [r for r in COMMITTED["rules"] if r["type"] != "pull_request"]},
    ):
        assert diff_ruleset(COMMITTED, weakened), (
            f"weakening not detected: {weakened.get('enforcement')}"
        )


def test_a_dropped_required_check_is_caught(tmp_path):
    thinner = json.loads(json.dumps(COMMITTED))
    for rule in thinner["rules"]:
        if rule["type"] == "required_status_checks":
            rule["parameters"]["required_status_checks"] = [{"context": "verify"}]
    differences = "\n".join(diff_ruleset(COMMITTED, thinner))
    assert "test-matrix (ubuntu-latest, 3.13)" in differences
    assert "not required live" in differences


def test_unreadable_live_config_says_so_instead_of_passing(monkeypatch, capsys):
    """The rule the whole issue turns on: an unreadable configuration is not a matching
    one. Every failure mode exits 2 with CANNOT VERIFY, never 0."""
    import check_ruleset

    for reason in ("gh not installed", "gh auth failed", "no ruleset exists"):

        def _boom(*_a, __reason=reason, **_k):
            raise CannotVerify(__reason)

        monkeypatch.setattr(check_ruleset, "fetch_live_ruleset", _boom)
        rc = check_main([])
        out = capsys.readouterr().out
        assert rc == CANNOT_VERIFY, f"{reason}: reported {rc}, must never be a pass"
        assert rc != 0
        assert "CANNOT VERIFY" in out
        assert reason in out
        assert "Nothing about the live ruleset is asserted by this run" in out


def test_a_missing_gh_binary_is_cannot_verify_not_a_pass(monkeypatch):
    import check_ruleset

    def _no_gh(*_a, **_k):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(check_ruleset.subprocess, "run", _no_gh)
    with pytest.raises(CannotVerify, match="not installed"):
        fetch_live_ruleset("owner/repo")


def test_an_empty_ruleset_list_is_cannot_verify_not_a_match(monkeypatch):
    """Empty output is what the old command produced. It must never read as agreement."""
    import check_ruleset

    monkeypatch.setattr(check_ruleset, "_run_gh", lambda _args: [])
    with pytest.raises(CannotVerify, match="no ruleset exists"):
        fetch_live_ruleset("owner/repo")


def test_a_ruleset_that_does_not_cover_main_is_cannot_verify(monkeypatch):
    import check_ruleset

    def _fake(args: list[str]):
        if args[-1].endswith("/rulesets"):
            return [{"id": 1}]
        return {
            "id": 1,
            "name": "other",
            "conditions": {"ref_name": {"include": ["refs/heads/dev"]}},
        }

    monkeypatch.setattr(check_ruleset, "_run_gh", _fake)
    with pytest.raises(CannotVerify, match="none covers"):
        fetch_live_ruleset("owner/repo")


def test_selection_is_by_target_so_a_rename_cannot_hide_it(monkeypatch):
    import check_ruleset

    def _fake(args: list[str]):
        if args[-1].endswith("/rulesets"):
            return [{"id": 99}]
        return {
            "id": 99,
            "name": "renamed-again",
            "conditions": {"ref_name": {"include": ["refs/heads/main"]}},
            "rules": [],
        }

    monkeypatch.setattr(check_ruleset, "_run_gh", _fake)
    assert fetch_live_ruleset("owner/repo")["name"] == "renamed-again"


def test_the_docs_no_longer_publish_the_check_that_cannot_fail():
    """`select(.name=="main")` may only appear as the named-and-explained mistake."""
    text = (ROOT / ".github" / "rulesets" / "README.md").read_text(encoding="utf-8")
    if 'select(.name=="main")' in text:
        assert "DO NOT USE" in text, "the broken command is republished without a warning"
    assert "make ruleset-check" in text
    assert "CANNOT VERIFY" in text


def test_the_docs_no_longer_claim_the_ruleset_is_unapplied():
    """Two files said the gates were advisory while they were being enforced."""
    ruleset_readme = (ROOT / ".github" / "rulesets" / "README.md").read_text(encoding="utf-8")
    assert "has been active on `main` since 2026-07-09" in ruleset_readme
    assert "advisory only" not in ruleset_readme.split("## What is actually enforced")[1]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    cicd_row = next(line for line in readme.splitlines() if line.startswith("| CI/CD |"))
    assert "not yet applied" not in cicd_row
    assert "is** active" in cicd_row or "**is** active" in cicd_row

    ledger = (ROOT / "docs" / "GAP-LEDGER.md").read_text(encoding="utf-8")
    cicd_entry = ledger.split("## GAP-CICD-1")[1].split("## GAP-A11Y-1")[0]
    assert "active on `main` since 2026-07-09" in cicd_entry
