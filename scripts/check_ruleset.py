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


class CannotVerify(Exception):
    """The live configuration could not be read. Never silently a pass."""


def _run_gh(args: list[str]) -> Any:
    """Call `gh api` and parse JSON, or raise CannotVerify with the reason."""
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            ["gh", *args],  # noqa: S607 - gh is resolved from PATH by design
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CannotVerify(
            "the GitHub CLI (`gh`) is not installed, so the live ruleset cannot be read"
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
    listing = _run_gh(["api", f"repos/{repo}/rulesets"])
    if not isinstance(listing, list):
        raise CannotVerify("the rulesets endpoint did not return a list")
    if not listing:
        raise CannotVerify(
            f"no ruleset exists on {repo}. Every merge-blocking gate in ci.yml is "
            "advisory until one is applied — see .github/rulesets/README.md"
        )
    covering: list[dict[str, Any]] = []
    for entry in listing:
        detail = _run_gh(["api", f"repos/{repo}/rulesets/{entry['id']}"])
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


def diff_ruleset(committed: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """Every way the live ruleset differs from the committed definition, in words."""
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

    differences = diff_ruleset(committed, live)
    if not differences:
        print(
            f"Live ruleset {live.get('name')!r} matches {RULESET_FILE.name} "
            f"({len(_contexts(live))} required checks, enforcement "
            f"{live.get('enforcement')!r})."
        )
        return 0

    print(
        f"Live ruleset {live.get('name')!r} (id {live.get('id')}) DIFFERS from "
        f"{RULESET_FILE.name} in {len(differences)} way(s):"
    )
    for line in differences:
        print(f"  - {line}")
    print(
        "\nDecide which is the intended posture and make the other match: update the "
        "live ruleset to the file, or amend the file to reality and rewrite the design "
        "notes it invalidates. See .github/rulesets/README.md."
    )
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
