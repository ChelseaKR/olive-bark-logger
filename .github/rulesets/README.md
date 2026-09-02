# Branch ruleset — what is live, and that this file now matches it

**A ruleset has been active on `main` since 2026-07-09**: `protect-main`
(id `18752850`, `enforcement: active`). **On 2026-08-21 the live ruleset and this file
were reconciled** — the live configuration was brought up to `main.json` for the
`pull_request` rule, strict required status checks, and `bypass_actors: []`, and
`main.json` was amended to drop `required_signatures` (decision note below) and to carry
the live ruleset's name. **On 2026-08-26 five of the eleven required status checks were
removed, because an `echo` was satisfying them** (see the next section). **On 2026-08-27
this file and the paragraphs below stopped saying "no bypass actors", because that had
become false: the repository-admin role can bypass every rule on this ruleset, always**
(see [The 2026-08-27 correction](#the-2026-08-27-correction-someone-can-bypass-and-two-documents-said-no-one-could)).
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
- **One bypass actor: the repository-admin role, always.** `bypass_actors` carries
  `{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}`. Everything
  above binds every contributor **except** an administrator, and on this repository the
  administrator is the owner, who is also the only human with write access. So for her
  these rules are a default she can step past on purpose, and for anyone else they are
  absolute. That is the deliberate posture — an owner who cannot recover a repository
  whose required check is wedged has a worse problem than an unreviewed merge — and it is
  written here because between 2026-08-21 and 2026-08-27 this page said the opposite.
- **Six required status checks** must report green: `verify` and five
  `test-matrix (ubuntu-latest, 3.9–3.13)`. Every one of them runs the repository's real
  gates and every one of them can fail. Six is both the count and the strength; before
  2026-08-26 the count was eleven and the strength was six.

## The 2026-08-27 correction: someone can bypass, and two documents said no one could

On 2026-08-27 the live ruleset answered `make ruleset-check` like this:

```
Live ruleset 'protect-main' (id 18752850) DIFFERS from main.json in 1 way(s):
  - bypass_actors: committed [] (no one bypasses), live ['RepositoryRole:5 (always)']
```

A `RepositoryRole:5 / always` bypass actor was added to this repository (and to every
repository in this portfolio) so that the owner can always merge past a wedged gate. The
same read reports `"current_user_can_bypass": "always"` for the maintainer's token, which
is the API stating the consequence directly.

`main.json` said `bypass_actors: []`. This page said "**No bypass actors.** No one —
including the repository owner — merges past these rules." Both were false from the
moment that actor was added, and both were false in the direction that flatters the
repository: they described a stricter gate than the one that exists. **The file has been
amended to the truth, not the ruleset to the file.** The owner's bypass is deliberate and
stays; a document that undersells who can merge is the thing that was wrong.

Two consequences worth stating rather than discovering later:

- **CI cannot catch this class of drift, and it is the only class it cannot catch.**
  `verify` runs `scripts/check_ruleset.py --scope public`, and the publicly readable view
  of a ruleset omits `bypass_actors` entirely. Every other field is checked on every pull
  request; this one is checked only by `make ruleset-check` with a maintainer token. The
  field that turned out to be wrong is exactly the field nothing automatic reads. The
  answer is not to pretend otherwise: `--scope public` prints "NOT CHECKED in this run:
  bypass actors" on its passing path, and the honest cadence is to run
  `make ruleset-check` locally after any change to repository administration.
- **`main.json` now records the bypass actor, so the check fails in both directions.**
  Adding a second bypass actor is a difference, and so is *removing* this one — which
  matters, because silently dropping the owner's recovery path would leave a repository
  nobody can unstick. `tests/test_ruleset_check.py` pins both.

The pattern this repeats is the one the 2026-08-26 section is about, with the sign
flipped. That change removed a gate that read as stronger than it was; this one removes a
*sentence* that read as stronger than it was. Prose does not block a merge — and prose
that overstates a gate is worse than no prose, because a reader stops looking.

### 2026-08-28: the comparison itself was the wrong shape

Recording the actor in `main.json` fixed the claim. It did not fix the check, which
compared the two bypass lists **by equality** — the one comparison that cannot see this
failure. If a later edit "tidied" the committed file back to `[]` on a day the owner had
also been locked out live, the two sides would agree and the check would report a match
on precisely the incident the field protects. Two wrong values that agree are the
failure mode; equality cannot distinguish them from two right ones.

`bypass_findings` in `scripts/check_ruleset.py` therefore holds **each side
independently** against the owner's bypass, and compares only *other* actors between
them:

- the owner's bypass missing from the **live** ruleset is the lockout recurring;
- the owner's bypass missing from the **committed file** is a lockout waiting for
  somebody to run the reapply command above, which is how the original incident
  happened;
- any *other* bypass actor — a team, a GitHub App, a second role — is a finding in
  either direction, which is the threat that was actually worth an equality check.

`test_both_sides_emptied_is_still_a_failure` pins the case equality got wrong: two
findings, not zero.

Why the owner keeps a bypass at all, stated once so it is not re-litigated: an agent
applied a ruleset with no bypass actor and locked the owner out of her own repository,
and restoring access took a sweep across eighteen repositories in this portfolio. An
empty `bypass_actors` list here is not a stricter gate — it is that incident. If you are
reading this because the empty list looks more secure and you are about to restore it:
do not.

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

(The bypass actor removed that day was a *user* bypass on the `pull_request` rule alone.
The `RepositoryRole:5 / always` actor live today is a different, later, deliberate one —
see the 2026-08-27 section. This paragraph describes what happened on 2026-08-21 and is
not a statement about the ruleset as it stands.)

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

> **Before running that, check that `main.json` still carries the owner's bypass actor.**
> This command replaces the live ruleset wholesale with the contents of the file. Until
> 2026-08-27 the file said `"bypass_actors": []` while the live ruleset carried the
> owner's standing bypass, so running it as written would have stripped that bypass and
> locked the owner out of the repository — by following this repository's own documented
> procedure. That is why the file is checked as something that will be *applied*, not
> only as a description of what is live: `make ruleset-check` fails when the file omits
> the owner's bypass, whatever the live ruleset says. Run it first.

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
- **`bypass_actors`: the repository-admin role, `bypass_mode: always`.** Recorded here
  since 2026-08-27, live since the day the portfolio-wide administrator bypass was added.
  Read it as what it is: **there is an emergency-merge path, and the owner is on it.**
  Everyone else is bound absolutely — a future second contributor has no way past a red
  required check — and the owner is bound by default and by habit, not by mechanism.

  This entry used to read `bypass_actors: []`, "no one — including repository admins —
  bypasses these rules", written as the direct fix for commit `74e6b8f` (2026-07-02), a
  direct-to-main push with no PR reference. That fix did its job and the maintainer's
  former `pull_request`-only user bypass is still gone. What replaced it is broader and
  deliberate, and the file said nothing about it for as long as it existed. The intent
  behind `74e6b8f`'s fix is now carried by habit and by the six required checks rather
  than by the absence of a bypass: when a required check goes red for a reason unrelated
  to the change (a stale nightly is the likeliest), the way through is still to fix the
  check — `gh workflow run nightly.yml --ref main` — and bypassing is a decision to make
  out loud, not the path of least resistance.

  **Never remove this actor to make a check pass.** It is the owner's stated requirement
  in every repository in this portfolio. If `make ruleset-check` reports it as a
  difference, the live ruleset lost it and needs it back; the file is not the thing to
  edit. Changing the posture in either direction means amending `main.json` and the live
  ruleset together and rewriting this note — and note that CI cannot see this field at
  all (`--scope public`), so only a local `make ruleset-check` will ever tell you.
