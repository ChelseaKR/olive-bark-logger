# Branch ruleset — definition, not a live setting

`main.json` in this directory is a **definition** the maintainer can apply; it has
**not** been applied to the GitHub repository. Activating it is a live branch-protection
API call, which is out of scope for an automated remediation pass (no write-effect
GitHub API calls) — this is a decision for a human to review and run themselves.

**Evidence this is needed:** commit `74e6b8f` (2026-07-02) is a direct-to-main push with
no PR reference. Until a ruleset like this is active, every "merge-blocking" gate in
`.github/workflows/ci.yml` is advisory only — nothing stops a `git push` straight to
`main` that skips CI entirely.

## To activate
Review `main.json`, then:
```bash
gh api --method POST repos/ChelseaKR/olive-bark-logger/rulesets \
  -H "Accept: application/vnd.github+json" \
  --input .github/rulesets/main.json
```
Confirm it landed and matches this file:
```bash
gh api repos/ChelseaKR/olive-bark-logger/rulesets --jq '.[] | select(.name=="main")'
```

## Design notes
- **`required_approving_review_count: 0`.** A solo maintainer cannot review their own
  PR under GitHub's own rules, so requiring ≥1 approval is unworkable, not just
  inconvenient — it would either lock the maintainer out entirely or force a
  meaningless bypass. `require_code_owner_review: true` still routes any *future*
  second contributor's changes through `CODEOWNERS`. See
  `docs/adr/0001-single-maintainer-review-posture.md` for the full reasoning and the
  trigger for revisiting this (a second maintainer joins).
- **`required_signatures`.** Requires signed commits. Set up local commit signing
  (`git config commit.gpgsign true` with a GPG key, or SSH signing) *before* activating
  this rule, or every future push will be rejected, including the maintainer's own.
- **`required_status_checks` contexts** list the current CI job names
  (`.github/workflows/ci.yml`: `verify` + all ten `test-matrix` legs). Update this list
  whenever a job is renamed or a new required job is added (e.g. once
  `docs/GAP-LEDGER.md#gap-sec-1` / `#gap-cicd-1` land CodeQL, zizmor, or Scorecard as
  separate jobs).
- **`bypass_actors: []`.** No one — including repository admins — bypasses these rules.
  This is the direct fix for the `74e6b8f` bypass evidence above.
