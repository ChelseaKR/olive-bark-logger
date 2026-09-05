"""The check that replaced five required status checks an `echo` used to satisfy.

Between 2026-07-09 and 2026-08-26 the `protect-main` ruleset required eleven contexts,
five of which -- `test-matrix (macos-latest, 3.9 .. 3.13)` -- were reported by
`test-matrix-macos-nightly-notice`, whose entire body was:

    - run: echo "macOS legs run on the nightly schedule (nightly.yml) per ... §11b"

The live API described it exactly: `labels: ["ubuntu-latest"]`, three steps, four
seconds, `conclusion: "success"`, on every commit. Those five contexts are gone, and
`scripts/check_nightly_macos.py` is what stands where they stood.

Everything here is offline. The payloads below are trimmed copies of real API responses
(nightly run 32938452292 and ci run 32648677865, both read on 2026-08-26), so the
assertions hold in CI without network or a token. The live question is answered by
`make nightly-check`, not by the test suite.

Written the way the gate tests in this repo are written: not only "it passes on a good
run", but a case for every way it must go red -- including the one that matters most,
a sweep whose jobs did not run on macOS at all.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from conftest import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

from check_nightly_macos import (
    MIN_MACOS_JOBS,
    assess,
    latest_completed_run,
    macos_jobs,
)
from check_nightly_macos import main as nightly_main
from check_ruleset import CANNOT_VERIFY, CannotVerify

NOW = datetime(2026, 8, 26, 22, 0, tzinfo=timezone.utc)

# nightly.yml run 32938452292 on main, trimmed to the fields the check reads.
GOOD_RUN = {
    "id": 32938452292,
    "name": "nightly",
    "status": "completed",
    "conclusion": "success",
    "head_branch": "main",
    "event": "schedule",
    "run_started_at": "2026-08-26T06:30:27Z",
    "updated_at": "2026-08-26T06:31:23Z",
    "html_url": "https://github.com/ChelseaKR/olive-bark-logger/actions/runs/32938452292",
}


def fresh_run(**overrides: object) -> dict:
    """`GOOD_RUN`, but recent as of whenever the suite runs.

    The `assess` tests below pass an explicit `NOW`, so they are deterministic and pin
    the freshness logic exactly. The end-to-end tests call `main()`, which reads the
    real clock, and against a fixture dated 2026-08-26 they aged out of the 168-hour
    window on 2026-09-02 and stayed red: the pass-path test failed, and the
    failure-path test went on passing for the wrong reason, because the staleness
    message names the same remedy the no-macOS-jobs message does.

    A fixture with a date in it is a test with an expiry date on it. This one carries a
    recency instead, which is the property the check actually reads.
    """
    started = datetime.now(timezone.utc) - timedelta(hours=1)
    return {
        **GOOD_RUN,
        "run_started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at": (started + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **overrides,
    }


# Its five jobs, as the jobs endpoint returned them. `labels` is the load-bearing field.
GOOD_JOBS = [
    {
        "name": f"test-matrix-macos (macos-latest, {py})",
        "conclusion": "success",
        "labels": ["macos-latest"],
    }
    for py in ("3.9", "3.10", "3.11", "3.12", "3.13")
]

# The five jobs that satisfied the five required contexts until 2026-08-26, as the same
# endpoint returned them for ci.yml run 32648677865. Same names, same green, same count.
# One field tells them apart, which is why this check reads that field.
PLACEHOLDER_JOBS = [
    {
        "name": f"test-matrix (macos-latest, {py})",
        "conclusion": "success",
        "labels": ["ubuntu-latest"],
    }
    for py in ("3.9", "3.10", "3.11", "3.12", "3.13")
]


def test_a_fresh_green_macos_sweep_supports_a_merge():
    """The other half of a real check: it must be able to pass, or it is noise."""
    assert assess(GOOD_RUN, GOOD_JOBS, NOW) == []


def test_the_echo_that_used_to_satisfy_five_required_checks_does_not_pass_this_one():
    """The regression, named. Five green jobs with the right names and the wrong runner
    is precisely what was merging PRs, and it must never read as macOS coverage again."""
    macos = [job for job in PLACEHOLDER_JOBS if "macos" in job["labels"][0]]
    assert macos == [], "the fixture is wrong: these jobs ran on ubuntu"
    problems = "\n".join(assess(GOOD_RUN, macos, NOW))
    assert "0 job(s)" in problems
    assert f"at least {MIN_MACOS_JOBS}" in problems


def test_a_shrunken_sweep_is_caught():
    """Quietly dropping legs is the slow version of the same defect."""
    problems = "\n".join(assess(GOOD_RUN, GOOD_JOBS[:2], NOW))
    assert f"at least {MIN_MACOS_JOBS}" in problems


def test_a_failed_sweep_blocks_the_merge():
    failing = [{**GOOD_JOBS[0], "conclusion": "failure"}, *GOOD_JOBS[1:]]
    problems = "\n".join(assess(GOOD_RUN, failing, NOW))
    assert "test-matrix-macos (macos-latest, 3.9)" in problems


def test_a_red_run_blocks_the_merge_even_with_five_macos_jobs():
    problems = "\n".join(assess({**GOOD_RUN, "conclusion": "failure"}, GOOD_JOBS, NOW))
    assert "'failure'" in problems


def test_a_stale_sweep_blocks_the_merge_and_says_how_stale():
    """A nightly that stopped running is the '0 of 156 sources for 37 days' shape: still
    green, still reporting, no longer looking at anything."""
    problems = "\n".join(assess(GOOD_RUN, GOOD_JOBS, NOW + timedelta(days=30)))
    assert "freshness window" in problems
    assert "30 days ago" in problems


def test_the_freshness_window_tolerates_a_missed_night():
    assert assess(GOOD_RUN, GOOD_JOBS, NOW + timedelta(days=2)) == []


def test_no_completed_run_at_all_is_a_failure_not_a_pass():
    problems = "\n".join(assess(None, [], NOW))
    assert "not running at all" in problems


def test_a_run_with_no_timestamp_is_not_quietly_fresh():
    without = {k: v for k, v in GOOD_RUN.items() if k != "updated_at"}
    problems = "\n".join(assess(without, GOOD_JOBS, NOW))
    assert "age is unknown" in problems


def test_an_unreadable_api_is_cannot_verify_not_a_pass(monkeypatch, capsys):
    """Same contract as the ruleset check: an unread workflow run is not a passing one."""
    import check_nightly_macos

    def _boom(*_a, **_k):
        raise CannotVerify("gh auth failed")

    monkeypatch.setattr(check_nightly_macos, "latest_completed_run", _boom)
    rc = nightly_main([])
    out = capsys.readouterr().out
    assert rc == CANNOT_VERIFY
    assert rc != 0
    assert "CANNOT VERIFY" in out
    assert "Nothing about the macOS sweep is asserted by this run" in out


def test_a_malformed_runs_payload_is_cannot_verify(monkeypatch):
    import check_nightly_macos

    monkeypatch.setattr(check_nightly_macos, "run_gh", lambda _args: {"unexpected": True})
    try:
        latest_completed_run("owner/repo")
    except CannotVerify as exc:
        assert "did not return a run list" in str(exc)
    else:  # pragma: no cover - the assertion below is the failure report
        raise AssertionError("a payload with no run list must never read as 'no runs'")


def test_a_malformed_jobs_payload_is_cannot_verify(monkeypatch):
    import check_nightly_macos

    monkeypatch.setattr(check_nightly_macos, "run_gh", lambda _args: {"unexpected": True})
    try:
        macos_jobs(1, "owner/repo")
    except CannotVerify as exc:
        assert "did not return a job list" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("a payload with no job list must never read as 'no macOS jobs'")


def test_an_in_progress_run_is_skipped_rather_than_read_as_the_result(monkeypatch):
    """The newest run is often still running. Reading its empty conclusion as a failure
    would make the gate flap; reading it as a pass would be worse."""
    import check_nightly_macos

    monkeypatch.setattr(
        check_nightly_macos,
        "run_gh",
        lambda _args: {
            "workflow_runs": [
                {
                    "id": 2,
                    "status": "in_progress",
                    "conclusion": None,
                    "updated_at": "2026-08-27T06:30:00Z",
                },
                GOOD_RUN,
            ]
        },
    )
    assert latest_completed_run("owner/repo") == GOOD_RUN


def test_the_pass_message_states_what_it_does_not_cover(monkeypatch, capsys):
    """The claim this makes is narrower than the five contexts it replaced implied, and
    it has to say so on the passing path, where nobody is looking for caveats."""
    import check_nightly_macos

    monkeypatch.setattr(check_nightly_macos, "latest_completed_run", lambda *_a, **_k: fresh_run())
    monkeypatch.setattr(check_nightly_macos, "macos_jobs", lambda *_a, **_k: GOOD_JOBS)
    rc = nightly_main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "real macOS runners" in out
    assert "NOT CHECKED by this gate: this pull request's own code on macOS" in out


def test_the_failure_message_names_the_remedy(monkeypatch, capsys):
    import check_nightly_macos

    monkeypatch.setattr(check_nightly_macos, "latest_completed_run", lambda *_a, **_k: fresh_run())
    monkeypatch.setattr(check_nightly_macos, "macos_jobs", lambda *_a, **_k: [])
    rc = nightly_main([])
    out = capsys.readouterr().out
    assert rc == 1
    assert "gh workflow run nightly.yml --ref main" in out


def test_the_workflow_it_watches_is_the_one_that_runs_macos():
    """A check pointed at the wrong file is a check that cannot fail. Read the workflow
    and confirm it both exists and actually asks for macOS runners."""
    from check_nightly_macos import WORKFLOW

    nightly = (ROOT / ".github" / "workflows" / WORKFLOW).read_text(encoding="utf-8")
    assert "macos-latest" in nightly
    assert "schedule:" in nightly


def test_ci_no_longer_reports_macos_contexts_from_an_ubuntu_runner():
    """The deleted job, pinned. `test-matrix-macos-nightly-notice` renamed itself to the
    five required macOS context names and ran on ubuntu-latest. Nothing in ci.yml may
    claim a macos context again without a macos runner behind it."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    # Comments are exempt on purpose: the file explains at length what was removed and
    # why, and that history is worth more in place than the tidiness of never naming it.
    directives = [line.strip() for line in ci.splitlines() if not line.lstrip().startswith("#")]
    assert not any("test-matrix-macos-nightly-notice" in line for line in directives), (
        "the always-green notice job is back in ci.yml"
    )

    # A job cannot report macOS results without a macOS runner, so this is the whole
    # question: does anything here ask for one? `runs-on:` and a matrix `os:` list are
    # the only two ways to.
    runner_lines = [line for line in directives if line.startswith(("runs-on:", "os:"))]
    assert runner_lines, "no runs-on/os lines found at all -- this test is not reading ci.yml"
    offenders = [line for line in runner_lines if "macos" in line.lower()]
    assert offenders == [], (
        "ci.yml asks for a macos runner again: "
        + "; ".join(offenders)
        + ". CI-CD-STANDARD §11b forbids macos on PR CI. The nightly sweep is where "
        "macOS coverage lives, and check_nightly_macos.py is how a merge leans on it."
    )
