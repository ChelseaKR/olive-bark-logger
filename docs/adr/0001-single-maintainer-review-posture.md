# 0001. Single-maintainer review posture

**Status:** Accepted · **Date:** 2026-07-05

## Context
`STANDARDS/CI-CD-STANDARD.md` expects a branch ruleset requiring ≥1 approving review
before merge (CICD-14/CICD-18, CQ-38/CQ-40). This repo has exactly one maintainer.
GitHub does not allow an author to approve their own pull request, so a literal
`required_approving_review_count: 1` (or more) with a single-person team is not a
stricter gate — it's a lock-out. The realistic choices are:
1. Require ≥1 review and grant the maintainer a standing bypass — but a standing
   bypass for the account that does 100% of the merges is equivalent to no rule at all,
   and is exactly the kind of self-certification the standard exists to prevent.
2. Waive the review-count requirement to 0, but keep every other rule (PR required,
   required status checks, no force-push, no branch deletion, no admin bypass, code-owner
   routing for any future second contributor).
3. Don't apply a ruleset at all — the status quo, evidenced by the direct-to-main push
   `74e6b8f` (2026-07-02) that this ADR exists to close.

## Decision
Option 2. `.github/rulesets/main.json` sets `required_approving_review_count: 0` and
`bypass_actors: []`. A PR is still mandatory, still has to pass every required status
check, and still cannot be force-pushed or bypassed by anyone — including the repo
owner. `require_code_owner_review: true` stays on so that `CODEOWNERS` routing takes
effect automatically the moment a second contributor ever opens a PR, with no ruleset
change needed at that point.

## Consequences
- **Easier:** the maintainer can still ship solo without being locked out of their own
  repo; CI still cannot be silently skipped by a raw push, which is the actual defect
  this ADR is responding to.
- **Harder / accepted risk:** no second pair of eyes reviews the maintainer's own PRs
  before merge. This is a conscious, documented gap (CQ-45), not a silent one — a human
  review requirement genuinely cannot substitute for a second human who doesn't exist.
- **Revisit trigger:** the moment a second maintainer joins this project, raise
  `required_approving_review_count` to 1 and remove this ADR's rationale from being the
  active posture (supersede this ADR with a new one rather than editing it in place).
