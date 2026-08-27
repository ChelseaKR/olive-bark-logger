# Branch ruleset — what is live, and that this file now matches it

**A ruleset has been active on `main` since 2026-07-09**: `protect-main`
(id `18752850`, `enforcement: active`). **On 2026-08-21 the live ruleset and this file
were reconciled** — the live configuration was brought up to `main.json` for the
`pull_request` rule, strict required status checks, and `bypass_actors: []`, and
`main.json` was amended to drop `required_signatures` (decision note below) and to carry
the live ruleset's name. **On 2026-08-26 five of the eleven required status checks were
removed, because an `echo` was satisfying them** (see the next section).
`make ruleset-check` exits 0 against the live API.

This document used to say the opposite — that nothing had been applied, and that "until a
ruleset like this is active, every merge-blocking gate in `.github/workflows/ci.yml` is
advisory only." That was wrong for over a month, and `ci.yml` disagreed with it in
writing the whole time: the `test-matrix-macos-nightly-notice` job existed *because* the
ruleset required five macOS contexts, and its comment said so.

## What is actually enforced on `main` right now

- **Deletion** and **non-fast-forward** (force-push) are blocked.
- **A pull request is required** — no direct pushes to `main` by anyone. Approvals
  required: 0 (solo-maintainer posture, ADR-0001); stale reviews are dismissed on push;
  review threads must be resolved; `CODEOWNERS` routing is on for any future second
  contributor.
- **Stale branches cannot merge** (`strict_required_status_checks_policy: true`): the
  branch must be up to date with `main` before merging.
- **No bypass actors.** No one — including the repository owner — merges past these
  rules. (Until 2026-08-21 the live ruleset granted the maintainer a `pull_request`
  bypass; it was removed in the reconciliation.)
- **Six required status checks** must report green: `verify` and five
  `test-matrix (ubuntu-latest, 3.9–3.13)`. Every one of them runs the repository's real
  gates and every one of them can fail. Six is both the count and the strength; before
  2026-08-26 the count was eleven and the strength was six.

## The 2026-08-26 change: five required checks that an `echo` satisfied

Until 2026-08-26 the ruleset also required five `test-matrix (macos-latest, 3.9–3.13)`
contexts. Nothing on a pull request ran macOS. What reported them was
`test-matrix-macos-nightly-notice` in `ci.yml`, a job that renamed itself to those five
context names and whose entire body was one `echo`. The live API described it without
help from anyone (`ci.yml` run 32648677865 on `main`, read 2026-08-26):

```
name:       test-matrix (macos-latest, 3.11)
labels:     ["ubuntu-latest"]
steps:      ["Set up job", "Run echo \"macOS legs run on the nightly...\"", "Complete job"]
duration:   4 seconds
conclusion: success
```

Five of eleven required checks could not fail, in any circumstance, ever. The ruleset
looked twice as strict as it was. The old text on this page conceded the point in prose
("the ruleset's real strength is six checks, not eleven") — but a documented fake gate is
still a fake gate, and prose does not block a merge.

**What changed:** the five contexts were removed from `main.json` and from the live
ruleset, and the notice job was deleted from `ci.yml`. No stand-in replaces it. A
required context whose job cannot fail is worse than an absent one, because it reads as
coverage.

**What replaced the coverage, and what did not.** CI-CD-STANDARD §11b forbids `macos-*`
runners on per-push/PR CI (10x minutes), so no honest per-PR macOS gate is available
here at all. Instead, two steps were added to the `verify` job — which is already a
required context, so they gained teeth without adding a check name:

- `scripts/check_nightly_macos.py` fails unless the nightly macOS sweep really ran on
  `main`, on runners the API labels `macos-*`, within seven days, and passed. The
  runner-label assertion is the specific defence against a repeat: a sweep reporting
  macOS results from an ubuntu runner is exactly what went wrong.
- `scripts/check_ruleset.py --scope public` fails unless the live ruleset still matches
  this file. That check already existed and was correct; it ran nowhere, so a PR that
  quietly rewrote `main.json` merged green.

The macOS gate is **lagging, and says so on every run**: a macOS-only regression
introduced by a PR still merges, the next nightly goes red, and from then on nothing
merges until it is fixed. That is a smaller claim than five green checks implied. It is
also a true one.

## The 2026-08-21 reconciliation, and the one rule deliberately dropped

Before 2026-08-21 the live ruleset was weaker than this file in four named ways
(`strict` false, `required_signatures` absent, no `pull_request` rule, one bypass
actor). Three were closed by bringing the live configuration up to the file. The fourth
went the other way, as a decision:

**`required_signatures` was removed from `main.json` rather than applied.** Commits in
this portfolio are routinely made by delegated agents on the maintainer's machines
without GPG/SSH *commit* signing configured, so requiring signed commits would reject
every push, including the maintainer's own. Release *tags* are signed elsewhere in the
portfolio (a dedicated release-signing key with committed `allowed_signers`
verification), which covers the artifact-provenance half of the intent. Turning commit
signing on remains a separate future decision: set up signing locally first, then add
the `required_signatures` rule back to `main.json` *and* the live ruleset in the same
change.

The committed file also now carries the live ruleset's name, `protect-main`, so the two
agree on identity as well as content.

## Checking it

```bash
make ruleset-check          # or: python scripts/check_ruleset.py
```

It selects the ruleset covering `refs/heads/main` **by target, not by name**, diffs it
against `main.json`, prints every difference, and exits:

- `0` — live matches this file
- `1` — live differs; each difference is named
- `2` — **CANNOT VERIFY**: `gh` missing, unauthenticated, API error, or no ruleset found

There is no path that exits 0 without having read the live configuration. That matters,
because the command this replaces could not fail:

```bash
# DO NOT USE — this is the check that was wrong.
gh api repos/ChelseaKR/olive-bark-logger/rulesets --jq '.[] | select(.name=="main")'
```

The live ruleset is named `protect-main`, so that printed nothing and exited 0. Empty
output from a confirm-it-landed command reads as "not applied", which is exactly the
wrong conclusion, and is presumably how both documents came to keep saying it. A check
that returns the same answer whether or not the thing exists is not a check.

`ruleset-check` is not part of `make verify`: it needs network access and an
authenticated `gh` with permission to read repository administration, neither of which a
*local* gate may assume. Run it when the ruleset or `ci.yml`'s job names change.

**CI does run it**, since 2026-08-26, as a step inside the required `verify` job:
`scripts/check_ruleset.py --scope public`. Two things follow from `--scope public`, and
both are printed by every such run rather than left here:

- The Actions `GITHUB_TOKEN` cannot be granted GitHub's `administration` permission —
  the permission simply is not offered to workflows. The rulesets endpoint answers it
  anyway, because this repository is public, but with a **reduced payload that omits
  `bypass_actors` entirely**.
- `.get("bypass_actors", [])` used to turn that omission into `[]`, i.e. "no one
  bypasses" — a pass drawn from a field that had never been read, in the one script
  written to refuse exactly that. Fixed on 2026-08-26: an absent field is CANNOT VERIFY
  under `--scope full`, and `--scope public` prints "NOT CHECKED in this run: bypass
  actors" on the passing path as well as the failing one.

So: **CI checks that the live ruleset still matches this file, except for bypass actors.
`make ruleset-check` with a maintainer token is the only thing that checks those.** Run
it after any change to repository administration.

The same job also runs `scripts/check_nightly_macos.py` (`make nightly-check`), which
holds the nightly macOS sweep to account. Same exit-code contract: `0` green and fresh,
`1` red, stale, shrunken, or not on macOS runners, `2` CANNOT VERIFY.

## Adding a required status check

One rule, learned the expensive way (see the 2026-08-26 section):

> **A context may be required only if the job reporting it can fail for a reason that
> matters.** Not "usually runs". Can fail. If the honest job cannot run on a pull
> request, do not require a stand-in for it — put a check that reads the honest job's
> real result into an existing required job instead, and have it state what it does not
> cover.

`tests/test_ruleset_check.py::test_the_placeholder_macos_contexts_are_no_longer_required`
and `tests/test_nightly_macos_check.py::test_ci_no_longer_reports_macos_contexts_from_an_ubuntu_runner`
pin the specific version of this that already happened. Neither can catch a *new*
placeholder under a new name; review is what catches that, which is why this paragraph
exists.

## Changing the ruleset from here on

`main.json` is the record; the live ruleset must match it. To change the posture: amend
`main.json` in a PR (with the design note that justifies it), then apply the same change
live:

```bash
gh api --method PUT repos/ChelseaKR/olive-bark-logger/rulesets/18752850 \
  -H "Accept: application/vnd.github+json" \
  --input .github/rulesets/main.json
```

Then `make ruleset-check` must print a match. Never change one side without the other:
the divergence this file spent a month documenting started exactly that way.

## Design notes (these describe `main.json`, the target)

- **`required_approving_review_count: 0`.** A solo maintainer cannot review their own
  PR under GitHub's own rules, so requiring ≥1 approval is unworkable, not just
  inconvenient — it would either lock the maintainer out entirely or force a
  meaningless bypass. `require_code_owner_review: true` still routes any *future*
  second contributor's changes through `CODEOWNERS`. See
  `docs/adr/0001-single-maintainer-review-posture.md` for the full reasoning and the
  trigger for revisiting this (a second maintainer joins). **Live since 2026-08-21.**
- **`required_signatures` — intentionally absent** since 2026-08-21; see the decision
  note above. Re-adding it requires commit signing to be configured first, or every
  push is rejected.
- **`required_status_checks` contexts** list the CI job names that do real work on a
  pull request (`.github/workflows/ci.yml`: `verify` + the five ubuntu `test-matrix`
  legs). Update this list whenever a job is renamed or a new required job is added (e.g.
  once `docs/GAP-LEDGER.md#gap-sec-1` / `#gap-cicd-1` land CodeQL, zizmor, or Scorecard
  as separate jobs), subject to the "Adding a required status check" rule above. **Live,
  and matching.**
- **`bypass_actors: []`.** No one — including repository admins — bypasses these rules.
  This was written as the direct fix for commit `74e6b8f` (2026-07-02), a direct-to-main
  push with no PR reference. **Live since 2026-08-21** — the maintainer's former
  `pull_request` bypass was removed in the reconciliation. Consequence worth naming:
  there is no emergency-merge path. If a required check goes red for a reason unrelated
  to the change (a stale nightly is the likeliest), the way through is to fix the check
  — `gh workflow run nightly.yml --ref main` — not to merge past it. Restoring a bypass
  actor is a deliberate posture change: amend `main.json` and the live ruleset together,
  and rewrite this note.
