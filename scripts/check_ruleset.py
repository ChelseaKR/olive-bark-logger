"""Diff the live branch ruleset on `main` against `.github/rulesets/main.json`.

This replaces a "verification step" that could not fail:

    gh api repos/ChelseaKR/olive-bark-logger/rulesets --jq '.[] | select(.name=="main")'

The live ruleset is named `protect-main`, so that command printed nothing and exited 0.
Empty output from a confirm-it-landed command reads as "not applied" — which is how two
files in this repo came to say the ruleset was never applied while a third was engineered
around the fact that it was. A check that returns the same answer whether or not the
thing exists is not a check.

This one selects by **target** (any ruleset covering `refs/heads/main`), not by name, so a
rename cannot hide it, and it reports the name mismatch as one of the differences.

Exit codes are the point:

    0  live matches the committed definition
    1  live differs — every difference is printed
    2  CANNOT VERIFY — gh missing, unauthenticated, API error, or no ruleset found

There is deliberately no path that exits 0 without having read the live configuration.

`--scope public` (2026-08-26) exists so CI can run this as a merge-blocking step. The
Actions `GITHUB_TOKEN` cannot be granted GitHub's `administration` permission, and the
reduced view of a ruleset omits `bypass_actors` altogether -- which `.get("bypass_actors",
[])` was quietly reading as "[], no one bypasses", a pass drawn from a field that was
never read. That hole is closed: an absent field is CANNOT VERIFY under `--scope full`,
and under `--scope public` every run prints, pass or fail, that bypass actors were not
among the things it checked.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

REPO = "ChelseaKR/olive-bark-logger"
RULESET_FILE = Path(__file__).resolve().parent.parent / ".github" / "rulesets" / "main.json"
MAIN_REF = "refs/heads/main"

CANNOT_VERIFY = 2

# Printed by every `--scope public` run, pass or fail. The run is genuinely narrower
# than a `--scope full` one and must not be quoted as if it were not.
_BYPASS_NOT_CHECKED = (
    "NOT CHECKED in this run: bypass actors. The publicly readable view of a ruleset "
    "omits `bypass_actors`, so nothing above asserts that no one can bypass these "
    "rules. `make ruleset-check` (--scope full, maintainer token) is what checks that."
)


class CannotVerify(Exception):
    """The live configuration could not be read. Never silently a pass."""


def run_gh(args: list[str]) -> Any:
    """Call `gh api` and parse JSON, or raise CannotVerify with the reason.

    Public because `check_nightly_macos.py` needs the same "an unreadable answer is
    never a passing one" behaviour, and two copies of it would be two things to keep
    honest.
    """
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            ["gh", *args],  # noqa: S607 - gh is resolved from PATH by design
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CannotVerify(
            "the GitHub CLI (`gh`) is not installed, so the live configuration cannot be read"
        ) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise CannotVerify(
            f"`gh {' '.join(args)}` failed: {detail[0] if detail else 'no output'}. "
            "Authenticate with `gh auth login` and make sure the token can read "
            "repository administration."
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CannotVerify(f"`gh {' '.join(args)}` returned output that is not JSON") from exc


def fetch_live_ruleset(repo: str = REPO) -> dict[str, Any]:
    """The live ruleset covering `refs/heads/main`, selected by target and not by name."""
    listing = run_gh(["api", f"repos/{repo}/rulesets"])
    if not isinstance(listing, list):
        raise CannotVerify("the rulesets endpoint did not return a list")
    if not listing:
        raise CannotVerify(
            f"no ruleset exists on {repo}. Every merge-blocking gate in ci.yml is "
            "advisory until one is applied — see .github/rulesets/README.md"
        )
    covering: list[dict[str, Any]] = []
    for entry in listing:
        detail = run_gh(["api", f"repos/{repo}/rulesets/{entry['id']}"])
        includes = detail.get("conditions", {}).get("ref_name", {}).get("include", [])
        if MAIN_REF in includes or "~DEFAULT_BRANCH" in includes or "~ALL" in includes:
            covering.append(detail)
    if not covering:
        raise CannotVerify(f"{len(listing)} ruleset(s) exist on {repo} but none covers {MAIN_REF}")
    if len(covering) > 1:
        names = ", ".join(sorted(r.get("name", "?") for r in covering))
        raise CannotVerify(
            f"more than one ruleset covers {MAIN_REF} ({names}); their combined effect "
            "cannot be diffed against a single committed definition"
        )
    return covering[0]


def _rule_types(ruleset: dict[str, Any]) -> set[str]:
    return {r.get("type", "") for r in ruleset.get("rules", [])}


def _rule(ruleset: dict[str, Any], rule_type: str) -> dict[str, Any] | None:
    for rule in ruleset.get("rules", []):
        if rule.get("type") == rule_type:
            return rule
    return None


def _contexts(ruleset: dict[str, Any]) -> set[str]:
    rule = _rule(ruleset, "required_status_checks")
    if rule is None:
        return set()
    params = rule.get("parameters", {})
    return {c.get("context", "") for c in params.get("required_status_checks", [])}


def _bypass(ruleset: dict[str, Any]) -> list[str]:
    return sorted(
        f"{a.get('actor_type', '?')}:{a.get('actor_id', '?')} ({a.get('bypass_mode', '?')})"
        for a in ruleset.get("bypass_actors", [])
    )


def bypass_is_visible(live: dict[str, Any]) -> bool:
    """Whether the response actually carries `bypass_actors`, rather than omitting it.

    The rulesets endpoint is readable on a public repository by anyone, including an
    unauthenticated caller and the Actions `GITHUB_TOKEN` (which cannot be granted the
    `administration` permission at all). That reduced view omits `bypass_actors`
    **entirely** -- verified against the live API on 2026-08-26. `.get("bypass_actors",
    [])` then turns the omission into "[] -- no one bypasses", which is exactly this
    script's own forbidden shape: a pass reported from a field that was never read. So
    the omission is distinguished from an empty list, and the caller decides.
    """
    return "bypass_actors" in live


def _diff_pull_request(committed: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """Differences in the `pull_request` rule's parameters.

    Only the keys the committed definition names are compared. The committed file is
    the assertion; the live rule also carries parameters GitHub defaults in
    (`required_reviewers`, `allowed_merge_methods`,
    `require_extra_approval_for_unattributed_changes`), and a new GitHub default must
    not turn a merge-blocking check red on its own. The cost of that choice, stated so
    it is not discovered later: deleting a key from `main.json` stops it being checked.
    """
    want, have = _rule(committed, "pull_request"), _rule(live, "pull_request")
    if want is None or have is None:
        return []  # a missing rule is already reported by the rule-type comparison
    want_params, have_params = want.get("parameters", {}), have.get("parameters", {})
    out: list[str] = []
    for key in sorted(want_params):
        if key not in have_params:
            out.append(f"pull_request.{key}: committed {want_params[key]!r}, absent from live")
        elif have_params[key] != want_params[key]:
            out.append(
                f"pull_request.{key}: committed {want_params[key]!r}, live {have_params[key]!r}"
            )
    return out


def _diff_status_checks(committed: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """Differences in the required-status-checks rule: the strict policy, and the list.

    The list is the part that decides whether a merge is gated on anything real, so
    every context that appears on one side and not the other is named individually.
    """
    out: list[str] = []
    want_checks, have_checks = (
        _rule(committed, "required_status_checks"),
        _rule(live, "required_status_checks"),
    )
    if want_checks and have_checks:
        want_strict = want_checks.get("parameters", {}).get("strict_required_status_checks_policy")
        have_strict = have_checks.get("parameters", {}).get("strict_required_status_checks_policy")
        if want_strict != have_strict:
            out.append(
                f"strict_required_status_checks_policy: committed {want_strict!r}, "
                f"live {have_strict!r} — live does not require the branch to be "
                "up to date before merging"
            )
    want_ctx, have_ctx = _contexts(committed), _contexts(live)
    for missing in sorted(want_ctx - have_ctx):
        out.append(f"required check {missing!r}: committed, not required live")
    for extra in sorted(have_ctx - want_ctx):
        out.append(f"required check {extra!r}: required live, not in the committed definition")
    return out


def diff_ruleset(
    committed: dict[str, Any], live: dict[str, Any], *, check_bypass: bool = True
) -> list[str]:
    """Every way the live ruleset differs from the committed definition, in words.

    `check_bypass=False` is for a caller that has already established the response
    cannot carry `bypass_actors` and has said so in its output. It narrows what is
    claimed; it never turns a difference into a match.
    """
    out: list[str] = []

    if committed.get("name") != live.get("name"):
        out.append(
            f"name: committed {committed.get('name')!r}, live {live.get('name')!r} "
            "— rename one so the two agree"
        )
    if committed.get("enforcement") != live.get("enforcement"):
        out.append(
            f"enforcement: committed {committed.get('enforcement')!r}, "
            f"live {live.get('enforcement')!r}"
        )

    want_rules, have_rules = _rule_types(committed), _rule_types(live)
    for missing in sorted(want_rules - have_rules):
        out.append(f"rule {missing!r}: in the committed definition, ABSENT from the live one")
    for extra in sorted(have_rules - want_rules):
        out.append(f"rule {extra!r}: live only, not in the committed definition")

    out.extend(_diff_status_checks(committed, live))
    out.extend(_diff_pull_request(committed, live))

    if check_bypass:
        want_bypass, have_bypass = _bypass(committed), _bypass(live)
        if want_bypass != have_bypass:
            out.append(
                f"bypass_actors: committed {want_bypass or '[] (no one bypasses)'}, "
                f"live {have_bypass or '[] (no one bypasses)'}"
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check-ruleset",
        description=(
            "Diff the live branch ruleset on main against .github/rulesets/main.json. "
            "Exits 1 on any difference and 2 when the live configuration cannot be read; "
            "never 0 without having read it."
        ),
    )
    parser.add_argument("--repo", default=REPO, help=f"owner/name (default: {REPO})")
    parser.add_argument(
        "--scope",
        choices=("full", "public"),
        default="full",
        help=(
            "full (default): every field, including bypass actors -- needs a token that "
            "can read repository administration. public: everything the reduced, "
            "publicly readable view carries, which is everything except bypass actors; "
            "the run says so in its own output. CI uses `public` because the Actions "
            "GITHUB_TOKEN cannot be granted the `administration` permission."
        ),
    )
    parser.add_argument(
        "--live-json",
        type=Path,
        default=None,
        help="read the live ruleset from a file instead of the API (for tests)",
    )
    args = parser.parse_args(argv)

    committed = json.loads(RULESET_FILE.read_text(encoding="utf-8"))
    try:
        if args.live_json is not None:
            live = json.loads(args.live_json.read_text(encoding="utf-8"))
        else:
            live = fetch_live_ruleset(args.repo)
    except CannotVerify as exc:
        print(f"CANNOT VERIFY: {exc}")
        print(
            "Reporting this rather than a pass: an unreadable configuration is not a "
            "matching one. Nothing about the live ruleset is asserted by this run."
        )
        return CANNOT_VERIFY

    check_bypass = args.scope == "full"
    if check_bypass and not bypass_is_visible(live):
        print(
            "CANNOT VERIFY: the ruleset came back with no `bypass_actors` field at all, "
            "which is what the API returns to a caller that cannot read repository "
            "administration. An absent field is not an empty one."
        )
        print(
            "Authenticate with a token that can read repository administration, or run "
            "with --scope public to check everything else and have the run say, out "
            "loud, that bypass actors were not checked."
        )
        return CANNOT_VERIFY

    differences = diff_ruleset(committed, live, check_bypass=check_bypass)
    if not differences:
        print(
            f"Live ruleset {live.get('name')!r} matches {RULESET_FILE.name} "
            f"({len(_contexts(live))} required checks, enforcement "
            f"{live.get('enforcement')!r})."
        )
        if not check_bypass:
            print(_BYPASS_NOT_CHECKED)
        return 0

    print(
        f"Live ruleset {live.get('name')!r} (id {live.get('id')}) DIFFERS from "
        f"{RULESET_FILE.name} in {len(differences)} way(s):"
    )
    for line in differences:
        print(f"  - {line}")
    if not check_bypass:
        print(_BYPASS_NOT_CHECKED)
    print(
        "\nDecide which is the intended posture and make the other match: update the "
        "live ruleset to the file, or amend the file to reality and rewrite the design "
        "notes it invalidates. See .github/rulesets/README.md."
    )
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
