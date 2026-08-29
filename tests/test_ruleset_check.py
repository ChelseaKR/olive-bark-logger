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
    OWNER_BYPASS,
    CannotVerify,
    bypass_findings,
    bypass_is_visible,
    diff_ruleset,
    fetch_live_ruleset,
)
from check_ruleset import main as check_main

COMMITTED = json.loads((ROOT / ".github" / "rulesets" / "main.json").read_text(encoding="utf-8"))

# The eleven contexts required from 2026-07-09 through 2026-08-26, five of which were
# `test-matrix (macos-latest, X)` and were reported by an `echo` on an ubuntu runner.
# Recorded rather than derived from main.json, because main.json no longer lists them
# and the tests below are about the transition away from them.
_CONTEXTS_THROUGH_2026_08_26 = [
    {"context": "verify"},
    *(
        {"context": f"test-matrix ({os_}, {py})"}
        for os_ in ("ubuntu-latest", "macos-latest")
        for py in ("3.9", "3.10", "3.11", "3.12", "3.13")
    ),
]


def _with_contexts(ruleset: dict, contexts: list[dict]) -> dict:
    """A copy of `ruleset` whose required_status_checks rule lists exactly `contexts`."""
    copied = json.loads(json.dumps(ruleset))
    for rule in copied["rules"]:
        if rule["type"] == "required_status_checks":
            rule["parameters"]["required_status_checks"] = json.loads(json.dumps(contexts))
    return copied


# The committed definition as it stood before the 2026-08-21 reconciliation: named
# "main", carrying required_signatures, and still listing all eleven contexts. Recorded
# so the historical-differences test keeps testing the defect it was written for after
# main.json was amended (required_signatures dropped as a decision, name aligned, and on
# 2026-08-26 the five placeholder macOS contexts removed).
COMMITTED_2026_08_15 = {
    **_with_contexts(COMMITTED, _CONTEXTS_THROUGH_2026_08_26),
    "name": "main",
    "rules": [
        {"type": "required_signatures"},
        *_with_contexts(COMMITTED, _CONTEXTS_THROUGH_2026_08_26)["rules"],
    ],
}

# The live ruleset as returned by the API after the 2026-08-21 reconciliation (trimmed to
# the fields the check reads). The offline twin of `make ruleset-check` exiting 0.
LIVE_2026_08_21 = {
    "id": 18752850,
    "name": "protect-main",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/main"]}},
    "rules": [
        {"type": "non_fast_forward"},
        {"type": "deletion"},
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 0,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": True,
                "require_last_push_approval": False,
                "required_review_thread_resolution": True,
            },
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
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
    "bypass_actors": [],
}

# The live ruleset after the 2026-08-26 change: identical to the 2026-08-21 one except
# that the five `test-matrix (macos-latest, X)` contexts are no longer required. That is
# the whole diff, so it is expressed as the whole diff rather than retyped. The offline
# twin of `make ruleset-check` exiting 0 today.
LIVE_2026_08_26 = _with_contexts(
    LIVE_2026_08_21,
    [{"context": "verify"}]
    + [
        {"context": f"test-matrix (ubuntu-latest, {py})"}
        for py in ("3.9", "3.10", "3.11", "3.12", "3.13")
    ],
)

# The live ruleset as the API returned it on 2026-08-28, byte for byte from
# `gh api repos/ChelseaKR/olive-bark-logger/rulesets/18752850`: the same six contexts as
# 2026-08-26, plus the repository owner's standing bypass. That bypass had been added
# live and this file still said `[]`, so nothing here matched reality until the file was
# corrected. **The live value is the correct one** -- see `OWNER_BYPASS` in
# `scripts/check_ruleset.py` and "Why the owner can bypass" in
# `.github/rulesets/README.md`. This is the offline twin of `make ruleset-check` exiting
# 0 today, and a check that failed against it would be a broken check, not a strict one.
LIVE_2026_08_28 = {**LIVE_2026_08_26, "bypass_actors": [OWNER_BYPASS]}

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
    """The four the issue enumerated, plus the name — against the definitions as they
    stood on 2026-08-15. Each named, not just counted. Pinned to the recorded committed
    definition of that date, because the current main.json was reconciled on 2026-08-21
    and no longer differs from the live ruleset."""
    differences = "\n".join(diff_ruleset(COMMITTED_2026_08_15, LIVE_2026_08_15))
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


def test_the_current_live_ruleset_matches_the_committed_definition(tmp_path, capsys):
    """The real configuration, held offline: the recorded live ruleset of 2026-08-28 and
    the current main.json agree. If either drifts, this fails before anyone needs the
    network to notice.

    This used to pin `LIVE_2026_08_26`, which recorded `bypass_actors: []`. That stopped
    being the live value once the owner's standing bypass was added, and the committed
    file said `[]` too -- so the pair agreed with each other while both disagreed with
    the repository. Pinning the *current* live payload is what makes this test a witness
    rather than a matching pair of stale copies.
    """
    rc = check_main(["--live-json", str(_write(tmp_path, LIVE_2026_08_28))])
    assert rc == 0
    assert "matches" in capsys.readouterr().out
    assert diff_ruleset(COMMITTED, LIVE_2026_08_28) == []


def test_the_placeholder_macos_contexts_are_no_longer_required():
    """The 2026-08-26 change itself, pinned so it cannot be quietly undone.

    Five required contexts -- `test-matrix (macos-latest, 3.9 .. 3.13)` -- were reported
    by `test-matrix-macos-nightly-notice`, a job whose only step was an `echo` and whose
    runner label was `ubuntu-latest`. They are gone from main.json, and putting any of
    them back without a job that can fail is the regression this test names.
    """
    contexts = {
        c["context"]
        for rule in COMMITTED["rules"]
        if rule["type"] == "required_status_checks"
        for c in rule["parameters"]["required_status_checks"]
    }
    placeholders = {c for c in contexts if "macos" in c}
    assert not placeholders, (
        "these contexts are required to merge again: "
        + ", ".join(sorted(placeholders))
        + ". CI-CD-STANDARD §11b forbids macos runners on PR CI, so nothing on a PR can "
        "report them honestly; the last job that did reported an echo. The nightly "
        "sweep is gated by `verify`'s check_nightly_macos.py step instead."
    )
    assert contexts, "a ruleset that requires nothing is not a gate either"
    # And the change is a removal, not a swap: the real legs are still required.
    assert "test-matrix (ubuntu-latest, 3.13)" in contexts
    assert "verify" in contexts


def test_the_2026_08_21_ruleset_no_longer_matches_the_file():
    """The witness for the change: the eleven-context ruleset that was live until
    2026-08-26 now differs from the committed definition, and the check names each of
    the five contexts that went away. A check that could not tell those two apart would
    be the same shape of defect as the job it removed."""
    differences = "\n".join(diff_ruleset(COMMITTED, LIVE_2026_08_21))
    for py in ("3.9", "3.10", "3.11", "3.12", "3.13"):
        assert f"test-matrix (macos-latest, {py})" in differences
    assert "required live, not in the committed definition" in differences


def test_a_weakened_ruleset_never_passes(tmp_path):
    """Each weakening on its own is caught -- not only the full set together."""
    for weakened in (
        {**COMMITTED, "enforcement": "disabled"},
        {
            **COMMITTED,
            "bypass_actors": [{"actor_id": 1, "actor_type": "User", "bypass_mode": "always"}],
        },
        {**COMMITTED, "rules": [r for r in COMMITTED["rules"] if r["type"] != "pull_request"]},
        {
            **COMMITTED,
            "rules": [
                {
                    **r,
                    "parameters": {
                        **r.get("parameters", {}),
                        "strict_required_status_checks_policy": False,
                    },
                }
                if r["type"] == "required_status_checks"
                else r
                for r in COMMITTED["rules"]
            ],
        },
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


# --- The reduced, publicly readable view of a ruleset ---------------------------------
#
# `GET /repos/{owner}/{repo}/rulesets/{id}` answers anyone on a public repository, and
# the Actions GITHUB_TOKEN is one of those anyones: GitHub has no `administration`
# permission a workflow can request. That reduced payload omits `bypass_actors`
# altogether (verified against the live API, 2026-08-26), and `.get("bypass_actors", [])`
# read the omission as "[] -- no one bypasses". A pass drawn from a field that was never
# read is the exact shape this whole script exists to refuse.


def _without_bypass(ruleset: dict) -> dict:
    reduced = json.loads(json.dumps(ruleset))
    reduced.pop("bypass_actors", None)
    return reduced


def test_an_absent_bypass_field_is_not_an_empty_one():
    assert bypass_is_visible(LIVE_2026_08_26)
    assert bypass_is_visible({"bypass_actors": [{"actor_id": 1}]})
    assert not bypass_is_visible(_without_bypass(LIVE_2026_08_26))


def test_full_scope_refuses_to_pass_a_ruleset_whose_bypass_actors_it_cannot_see(tmp_path, capsys):
    """The hole this closes: before, this input exited 0 and read as a full match."""
    rc = check_main(["--live-json", str(_write(tmp_path, _without_bypass(LIVE_2026_08_26)))])
    out = capsys.readouterr().out
    assert rc == CANNOT_VERIFY
    assert "CANNOT VERIFY" in out
    assert "bypass_actors" in out
    assert "An absent field is not an empty one" in out


def test_public_scope_passes_but_says_what_it_did_not_check(tmp_path, capsys):
    """CI's mode. It may pass -- and it may never imply it checked bypass actors."""
    rc = check_main(
        [
            "--scope",
            "public",
            "--live-json",
            str(_write(tmp_path, _without_bypass(LIVE_2026_08_26))),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "matches" in out
    assert "NOT CHECKED in this run: bypass actors" in out


def test_public_scope_still_catches_every_other_weakening(tmp_path, capsys):
    """Narrowing the claim must not narrow the teeth: the drift CI exists to catch is
    still caught, and the disclaimer rides along with the failure too."""
    drifted = _without_bypass(_with_contexts(LIVE_2026_08_26, [{"context": "verify"}]))
    rc = check_main(["--scope", "public", "--live-json", str(_write(tmp_path, drifted))])
    out = capsys.readouterr().out
    assert rc == 1
    assert "test-matrix (ubuntu-latest, 3.13)" in out
    assert "NOT CHECKED in this run: bypass actors" in out


def test_the_pull_request_rule_parameters_are_compared(tmp_path):
    """`require_code_owner_review` flipping off live was invisible until 2026-08-26:
    only the presence of the `pull_request` rule was compared, never its parameters."""
    for key, weaker in (
        ("require_code_owner_review", False),
        ("required_review_thread_resolution", False),
        ("dismiss_stale_reviews_on_push", False),
    ):
        weakened = json.loads(json.dumps(LIVE_2026_08_26))
        for rule in weakened["rules"]:
            if rule["type"] == "pull_request":
                rule["parameters"][key] = weaker
        differences = "\n".join(diff_ruleset(COMMITTED, weakened))
        assert f"pull_request.{key}" in differences, f"{key} weakened live, not reported"


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

    monkeypatch.setattr(check_ruleset, "run_gh", lambda _args: [])
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

    monkeypatch.setattr(check_ruleset, "run_gh", _fake)
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

    monkeypatch.setattr(check_ruleset, "run_gh", _fake)
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
    # Either shape is honest: "a ruleset is active" (2026-08-15 wording) or, since the
    # 2026-08-21 reconciliation, "the live ruleset matches the committed definition".
    assert "is** active" in cicd_row or "**is** active" in cicd_row or "**matches**" in cicd_row

    ledger = (ROOT / "docs" / "GAP-LEDGER.md").read_text(encoding="utf-8")
    cicd_entry = ledger.split("## GAP-CICD-1")[1].split("## GAP-A11Y-1")[0]
    assert "active on `main` since 2026-07-09" in cicd_entry


# --- The owner's standing bypass ------------------------------------------------------
#
# `bypass_actors` is the one field not compared by equality. The owner keeps a standing
# `RepositoryRole` 5 / `always` bypass, deliberately and permanently: an agent once
# applied a ruleset with no bypass and locked the owner out of their own repository, and
# restoring access took a sweep across eighteen repositories. This file and the live
# ruleset are each held against that actor independently, because two wrong values that
# agree with each other is the failure mode equality cannot see -- and this repository
# publishes a `--method PUT --input .github/rulesets/main.json` reapply procedure, which
# is exactly how an omission in the file becomes a lockout on the repository.


def test_the_committed_file_on_disk_records_the_owner_bypass():
    """Not a fixture: the actual `.github/rulesets/main.json`. Reapplying a ruleset file
    that omits the owner's bypass is how the lockout happens, so the file has to be
    right, not only the comparison."""
    assert COMMITTED["bypass_actors"] == [OWNER_BYPASS]


def test_the_real_live_configuration_is_a_match_not_a_finding():
    """A check that failed forever against a correct repository would not be a stricter
    check, it would be a broken one."""
    assert bypass_findings(COMMITTED, LIVE_2026_08_28) == []


def test_a_second_bypass_actor_is_reported():
    """The threat actually worth guarding: a team, a GitHub App or a second role handed
    the ability to skip these rules."""
    for extra in (
        {"actor_id": 4242, "actor_type": "Team", "bypass_mode": "pull_request"},
        {"actor_id": 99, "actor_type": "Integration", "bypass_mode": "always"},
        {"actor_id": 2, "actor_type": "RepositoryRole", "bypass_mode": "always"},
    ):
        drifted = {**LIVE_2026_08_28, "bypass_actors": [OWNER_BYPASS, extra]}
        found = bypass_findings(COMMITTED, drifted)
        assert len(found) == 1, found
        assert "unreviewed bypass actor" in found[0]
        assert str(extra["actor_id"]) in found[0], "the finding names the actor"


def test_the_owner_losing_their_bypass_is_reported():
    """The incident the rule exists for. An empty bypass list coming back from the API is
    the owner locked out of their own repository, however tidy the committed file looks."""
    found = bypass_findings(COMMITTED, {**LIVE_2026_08_28, "bypass_actors": []})
    assert len(found) == 1, found
    assert "is NOT enforced live" in found[0]
    assert "lockout" in found[0]


def test_both_sides_emptied_is_still_a_failure():
    """The case equality alone would pass, and the whole reason the owner's bypass is
    asserted against each side rather than only compared between them: a tidy revert of
    the committed file, on a day the owner had also been locked out, would otherwise
    report a match on exactly the incident this guards. Two findings, not zero."""
    found = bypass_findings(
        {**COMMITTED, "bypass_actors": []}, {**LIVE_2026_08_28, "bypass_actors": []}
    )
    assert len(found) == 2, found
    assert any("is NOT enforced live" in line for line in found), found
    assert any("no longer records" in line for line in found), (
        "the committed file losing the owner's bypass must be named too"
    )


def test_the_lockout_is_a_non_zero_exit_and_not_only_a_list(tmp_path, capsys):
    """End to end through the CLI, since a finding nobody exits non-zero on is advice."""
    rc = check_main(
        ["--live-json", str(_write(tmp_path, {**LIVE_2026_08_28, "bypass_actors": []}))]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "DIFFERS" in out
    assert "lockout" in out


def test_public_scope_never_claims_to_have_checked_the_owner_bypass(tmp_path, capsys):
    """CI's mode cannot see `bypass_actors` at all, so it must not imply the owner's
    bypass was verified -- in either direction."""
    rc = check_main(
        [
            "--scope",
            "public",
            "--live-json",
            str(_write(tmp_path, _without_bypass(LIVE_2026_08_28))),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "NOT CHECKED in this run: bypass actors" in out
    assert "lockout" not in out
