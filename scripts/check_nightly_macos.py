"""Hold the nightly macOS sweep to account, at merge time.

CI-CD-STANDARD §11b forbids `macos-*` runners on per-push/PR CI (10x minutes), so this
repo's macOS legs run on a schedule instead (`.github/workflows/nightly.yml`). Until
2026-08-26 the branch ruleset squared that circle by *requiring* five
`test-matrix (macos-latest, X)` contexts and satisfying them from
`test-matrix-macos-nightly-notice` -- a job that ran one `echo`. The live API stated the
problem better than any prose could: on the last `main` run of `ci.yml` before this
change, those five required checks reported

    labels:     ["ubuntu-latest"]
    steps:      ["Set up job", "Run echo \\"macOS legs run on the nightly...\\"", "Complete job"]
    duration:   4 seconds
    conclusion: success

Five of eleven required status checks could not fail. They are gone. This is what
replaces them, and it is deliberately a *weaker* claim than they implied:

    the nightly macOS sweep really ran on `main`, on real macOS runners, recently,
    and passed.

What this does NOT do, said plainly because the arrangement it replaces implied
otherwise: it does not run the pull request's own code on macOS. Nothing that respects
§11b can. A macOS-only regression introduced by a PR still merges; the next nightly goes
red, and from then on this check blocks every merge until it is fixed. That is a lagging
gate. A lagging gate that can fail is worth more than a per-PR gate that cannot.

The macOS-runner assertion is the part that matters most for the defect this repo just
had: a sweep that reported macOS results from an ubuntu runner is precisely what went
wrong, and `labels` is how the API tells you, without heuristics about durations.

Exit codes:

    0  the sweep ran on macOS runners inside the freshness window and passed
    1  it did not -- every reason is printed, with the one-line remedy
    2  CANNOT VERIFY -- gh missing, unauthenticated, or the API errored

There is no path that exits 0 without having read a real workflow run.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

from check_ruleset import CANNOT_VERIFY, CannotVerify, run_gh

REPO = "ChelseaKR/olive-bark-logger"
WORKFLOW = "nightly.yml"
BRANCH = "main"

# Seven days, not one: the schedule is daily, so this tolerates a week of missed or
# skipped runs before it starts blocking merges, and GitHub disables `schedule`
# triggers on public repositories after a stretch of inactivity. When it does start
# blocking, `gh workflow run nightly.yml --ref main` clears it in about two minutes.
MAX_AGE_HOURS = 168

# The number of macOS legs the nightly matrix is expected to run: one per supported
# Python version (pyproject.toml's >=3.9 floor through 3.13). Written as a floor, so
# adding a version does not fail the check, but quietly shrinking the sweep does.
MIN_MACOS_JOBS = 5

# How many recent runs to look through for a completed one. A generous window, so a
# single in-progress run does not read as "the sweep never ran".
RUNS_TO_SCAN = 20


def _parse_ts(value: str) -> datetime:
    """GitHub's ISO-8601 with a `Z` suffix, which 3.9's fromisoformat cannot take."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def latest_completed_run(
    repo: str = REPO, workflow: str = WORKFLOW, branch: str = BRANCH
) -> dict[str, Any] | None:
    """The most recently finished run of `workflow` on `branch`, or None if there is none."""
    payload = run_gh(
        [
            "api",
            f"repos/{repo}/actions/workflows/{workflow}/runs"
            f"?branch={branch}&per_page={RUNS_TO_SCAN}",
        ]
    )
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        raise CannotVerify(
            f"the workflow-runs endpoint for {workflow} did not return a run list; "
            "nothing about the nightly sweep is asserted by this run"
        )
    completed = [r for r in runs if isinstance(r, dict) and r.get("status") == "completed"]
    if not completed:
        return None
    return max(completed, key=lambda r: str(r.get("updated_at") or ""))


def macos_jobs(run_id: int, repo: str = REPO) -> list[dict[str, Any]]:
    """The jobs of `run_id` that actually ran on a macOS runner, per the API's own labels."""
    payload = run_gh(["api", f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"])
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise CannotVerify(
            f"the jobs endpoint for run {run_id} did not return a job list; "
            "nothing about the nightly sweep is asserted by this run"
        )
    return [job for job in jobs if _ran_on_macos(job)]


def _age_words(age: timedelta) -> str:
    """An age a reader can act on: hours under a day, days above it. Never "0 days"."""
    hours = age.total_seconds() / 3600
    return f"{hours:.1f}h" if hours < 24 else f"{age.days} days"


def _ran_on_macos(job: dict[str, Any]) -> bool:
    labels = job.get("labels") or []
    return any(str(label).lower().startswith("macos") for label in labels)


def assess(
    run: dict[str, Any] | None,
    jobs: list[dict[str, Any]],
    now: datetime,
    *,
    max_age_hours: int = MAX_AGE_HOURS,
    min_macos_jobs: int = MIN_MACOS_JOBS,
) -> list[str]:
    """Every reason the sweep does not support a merge, in words. Empty means it does."""
    if run is None:
        return [
            f"no completed run of {WORKFLOW} on {BRANCH} in the last {RUNS_TO_SCAN} runs. "
            "The macOS sweep is not running at all, so no merge can lean on it."
        ]

    problems: list[str] = []

    conclusion = run.get("conclusion")
    if conclusion != "success":
        problems.append(
            f"the last completed run ({run.get('html_url') or run.get('id')}) concluded "
            f"{conclusion!r}, not 'success'"
        )

    finished = str(run.get("updated_at") or "")
    if not finished:
        problems.append("the last completed run carries no `updated_at`, so its age is unknown")
    else:
        age = now - _parse_ts(finished)
        if age > timedelta(hours=max_age_hours):
            problems.append(
                f"the last completed run finished {_age_words(age)} ago "
                f"({finished}), past the {max_age_hours}h freshness window"
            )

    if len(jobs) < min_macos_jobs:
        problems.append(
            f"only {len(jobs)} job(s) in that run carried a macOS runner label, expected at "
            f"least {min_macos_jobs}. A sweep that reports macOS results from a non-macOS "
            "runner is the exact defect the five removed `test-matrix (macos-latest, X)` "
            "contexts were"
        )

    failed = sorted(
        str(job.get("name")) for job in jobs if job.get("conclusion") not in ("success", "skipped")
    )
    if failed:
        problems.append("macOS legs that did not pass: " + ", ".join(failed))

    return problems


def _describe_pass(run: dict[str, Any], jobs: list[dict[str, Any]], now: datetime) -> str:
    age = _age_words(now - _parse_ts(str(run["updated_at"])))
    return (
        f"Nightly macOS sweep: run {run.get('id')} on {BRANCH} passed {age} ago, "
        f"with {len(jobs)} job(s) on real macOS runners."
    )


NOT_CHECKED = (
    "NOT CHECKED by this gate: this pull request's own code on macOS. CI-CD-STANDARD "
    "§11b forbids macos runners on PR CI, so the sweep is nightly and this check is a "
    "lagging one -- a macOS-only regression merges, and blocks every merge after the "
    "next nightly catches it. See .github/rulesets/README.md."
)

REMEDY = (
    "Remedy: `gh workflow run nightly.yml --ref main`, wait for it to finish, then "
    "re-run this job. If the sweep is genuinely broken, fix it -- that is what this "
    "check is for."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check-nightly-macos",
        description=(
            "Fail unless the nightly macOS sweep ran on real macOS runners, recently, and "
            "passed. Exits 2 when the live configuration cannot be read; never 0 without "
            "having read a real workflow run."
        ),
    )
    parser.add_argument("--repo", default=REPO, help=f"owner/name (default: {REPO})")
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=MAX_AGE_HOURS,
        help=f"freshness window for the last completed run (default: {MAX_AGE_HOURS})",
    )
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    try:
        run = latest_completed_run(args.repo)
        jobs = macos_jobs(int(run["id"]), args.repo) if run is not None else []
    except CannotVerify as exc:
        print(f"CANNOT VERIFY: {exc}")
        print(
            "Reporting this rather than a pass: an unread workflow run is not a passing "
            "one. Nothing about the macOS sweep is asserted by this run."
        )
        return CANNOT_VERIFY

    problems = assess(run, jobs, now, max_age_hours=args.max_age_hours)
    if problems or run is None:
        print(f"The nightly macOS sweep does not support a merge, in {len(problems)} way(s):")
        for line in problems:
            print(f"  - {line}")
        print(f"\n{REMEDY}")
        print(NOT_CHECKED)
        return 1

    print(_describe_pass(run, jobs, now))
    print(NOT_CHECKED)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
