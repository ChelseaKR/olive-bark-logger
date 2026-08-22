# Branch ruleset — what is live, and that this file now matches it

**A ruleset has been active on `main` since 2026-07-09**: `protect-main`
(id `18752850`, `enforcement: active`). **On 2026-08-21 the live ruleset and this file
were reconciled** — the live configuration was brought up to `main.json` for the
`pull_request` rule, strict required status checks, and `bypass_actors: []`, and
`main.json` was amended to drop `required_signatures` (decision note below) and to carry
the live ruleset's name. `make ruleset-check` exits 0 against the live API.

This document used to say the opposite — that nothing had been applied, and that "until a
ruleset like this is active, every merge-blocking gate in `.github/workflows/ci.yml` is
advisory only." That was wrong for over a month, and `ci.yml` disagreed with it in
writing the whole time: the `test-matrix-macos-nightly-notice` job exists *because* the
ruleset requires five macOS contexts, and its comment says so.

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
- **Eleven required status checks** must report green: `verify`, five
  `test-matrix (ubuntu-latest, 3.9–3.13)`, and five `test-matrix (macos-latest, 3.9–3.13)`.

  Read that number honestly: the five macOS contexts are reported by
  `test-matrix-macos-nightly-notice`, an `echo` on an ubuntu runner that stands in for
  the real macOS sweep now running on the nightly schedule. So the ruleset's real
  strength is **six** checks, not eleven, and a nightly macOS failure does not block a
  merge. That arrangement is deliberate and documented in `ci.yml`; the point here is
  that "eleven required checks" would overstate it.

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
authenticated `gh` with permission to read repository administration, neither of which
`verify` may assume. Run it when the ruleset or `ci.yml`'s job names change.

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
- **`required_status_checks` contexts** list the current CI job names
  (`.github/workflows/ci.yml`: `verify` + all ten `test-matrix` legs). Update this list
  whenever a job is renamed or a new required job is added (e.g. once
  `docs/GAP-LEDGER.md#gap-sec-1` / `#gap-cicd-1` land CodeQL, zizmor, or Scorecard as
  separate jobs). **Live, and matching.**
- **`bypass_actors: []`.** No one — including repository admins — bypasses these rules.
  This was written as the direct fix for commit `74e6b8f` (2026-07-02), a direct-to-main
  push with no PR reference. **Live since 2026-08-21** — the maintainer's former
  `pull_request` bypass was removed in the reconciliation.
