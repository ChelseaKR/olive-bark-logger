# Branch ruleset — what is live, and how this file differs from it

**A ruleset has been active on `main` since 2026-07-09.** It is named `protect-main`
(id `18752850`, last updated 2026-07-19, `enforcement: active`), and it is **not** this
file. Verified 2026-08-15 with `make ruleset-check`.

This document used to say the opposite — that nothing had been applied, and that "until a
ruleset like this is active, every merge-blocking gate in `.github/workflows/ci.yml` is
advisory only." That was wrong for over a month, and `ci.yml` disagreed with it in
writing the whole time: the `test-matrix-macos-nightly-notice` job exists *because* the
ruleset requires five macOS contexts, and its comment says so.

## What is actually enforced on `main` right now

- **Deletion** and **non-fast-forward** (force-push) are blocked.
- **Eleven required status checks** must report green: `verify`, five
  `test-matrix (ubuntu-latest, 3.9–3.13)`, and five `test-matrix (macos-latest, 3.9–3.13)`.

  Read that number honestly: the five macOS contexts are reported by
  `test-matrix-macos-nightly-notice`, an `echo` on an ubuntu runner that stands in for
  the real macOS sweep now running on the nightly schedule. So the ruleset's real
  strength is **six** checks, not eleven, and a nightly macOS failure does not block a
  merge. That arrangement is deliberate and documented in `ci.yml`; the point here is
  that "eleven required checks" would overstate it.

## How the live ruleset is weaker than this file

`main.json` is the **intended** definition, kept here as the target. It is not a record
of the live state. Four differences, all of them things the live configuration lacks:

| | committed `main.json` | live `protect-main` |
|---|---|---|
| name | `main` | `protect-main` |
| `deletion`, `non_fast_forward` | yes | yes |
| `required_status_checks` | 11 contexts | same 11 contexts |
| `strict_required_status_checks_policy` | `true` | **`false`** — a stale branch can merge |
| `required_signatures` | yes | **absent** |
| `pull_request` rule (dismiss stale reviews, code-owner review, thread resolution) | yes | **absent** |
| `bypass_actors` | `[]` | **one user (`ChelseaKR`), `bypass_mode: pull_request`** |

The bypass is the one to weigh: `bypass_mode: pull_request` does not permit a direct push
to `main`, but it does let the maintainer merge a pull request past the required checks —
the specific thing `bypass_actors: []` was written to prevent.

Nothing in this list was chosen against the design notes below; the live ruleset was
created separately and the two were never reconciled.

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
authenticated `gh` with permission to read repository administration, neither of which
`verify` may assume. Run it when the ruleset or `ci.yml`'s job names change.

## Closing the gap

Two ways, and they are not equivalent:

1. **Bring the live ruleset up to this file** (the stronger posture). Adding
   `required_signatures` means setting up commit signing *first* — see the design note
   below — or every future push is rejected, including the maintainer's own. Applying
   the rest is a live API call, a deliberate human action, not something an automated
   pass should perform:

   ```bash
   gh api --method PUT repos/ChelseaKR/olive-bark-logger/rulesets/18752850 \
     -H "Accept: application/vnd.github+json" \
     --input .github/rulesets/main.json
   ```

   Then `make ruleset-check` should print a match.

2. **Accept the live posture** and amend `main.json` to it, rewriting the design notes
   that no longer describe anything. Honest, but it drops signed commits and the
   no-bypass stance, both of which were written down on purpose. Do this only as a
   decision, not as a way to make the checker green.

Either way, rename one so the two agree.

## Design notes (these describe `main.json`, the target)

- **`required_approving_review_count: 0`.** A solo maintainer cannot review their own
  PR under GitHub's own rules, so requiring ≥1 approval is unworkable, not just
  inconvenient — it would either lock the maintainer out entirely or force a
  meaningless bypass. `require_code_owner_review: true` still routes any *future*
  second contributor's changes through `CODEOWNERS`. See
  `docs/adr/0001-single-maintainer-review-posture.md` for the full reasoning and the
  trigger for revisiting this (a second maintainer joins). **Not live today.**
- **`required_signatures`.** Requires signed commits. Set up local commit signing
  (`git config commit.gpgsign true` with a GPG key, or SSH signing) *before* activating
  this rule, or every future push will be rejected, including the maintainer's own.
  **Not live today.**
- **`required_status_checks` contexts** list the current CI job names
  (`.github/workflows/ci.yml`: `verify` + all ten `test-matrix` legs). Update this list
  whenever a job is renamed or a new required job is added (e.g. once
  `docs/GAP-LEDGER.md#gap-sec-1` / `#gap-cicd-1` land CodeQL, zizmor, or Scorecard as
  separate jobs). **Live, and matching** — this is the one rule the two agree on.
- **`bypass_actors: []`.** No one — including repository admins — bypasses these rules.
  This was written as the direct fix for commit `74e6b8f` (2026-07-02), a direct-to-main
  push with no PR reference. **Not live today:** the live ruleset grants the maintainer a
  `pull_request` bypass. Direct pushes to `main` are blocked regardless, since that
  bypass mode does not cover them.
