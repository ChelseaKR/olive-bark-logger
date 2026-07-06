# Definition of Done

Protected by `.github/CODEOWNERS` (once the ruleset in `.github/rulesets/main.json` is
applied — see that file's header). Lifted from `README.md`'s one-line DoD and
`docs/ROADMAP.md` §7's gate table (QM-18); this is the canonical, expanded version.

## Every change
- [ ] `make verify` passes locally (lint, strict types, ≥85% branch coverage, security —
      bandit + pip-audit + gitleaks, structural a11y + pa11y/axe, PWA tests, i18n gate).
- [ ] `tests/test_no_audio.py`, `tests/test_no_egress.py`, and
      `tests/test_report_content.py` still pass, unmodified in intent — if your change
      touches any of them, the PR description explains why, not just what.
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]`.
- [ ] Any expensive-to-reverse decision (new dependency, schema change, declaring
      something N/A, changing a documented floor/threshold) has an ADR under
      `docs/adr/`.
- [ ] If you changed the report template, the PWA, or anything `docs/audits/*`
      describes, the corresponding dated artifact is regenerated (not just source code
      — see "Release checklist" below and `docs/GAP-LEDGER.md#gap-a11y-1--accessibility-scan-the-pwa-lighthouse-ci-regenerate-the-stale-walkthrough-acrvpat`
      for what happens when this step is skipped).

## Feature-complete for the monitor
The monitor runs unattended, logs noise events (levels + timestamps, zero audio) to
local SQLite, and produces an honest, accessible report with charts and a stated
methodology — all **applicable** `/STANDARDS` gates green (see `README.md`'s Standards
Conformance table for what "applicable" resolves to today) and the no-audio test
passing.

## Release checklist (when cutting a tagged version — see `docs/GAP-LEDGER.md#gap-rel-1--release--versioning-the-releasesupply-chain-pipeline-is-still-absent`)
- [ ] `make verify` passes at the tagged commit.
- [ ] `CHANGELOG.md` has a dated `## [X.Y.Z] - YYYY-MM-DD` section (move it out of
      `[Unreleased]`).
- [ ] `CITATION.cff`'s `version` and `date-released` are updated together, in the same
      PR as the tag.
- [ ] The a11y walkthrough (`docs/a11y/STATEMENT.md` + `docs/audits/accessibility-*.md`)
      is regenerated if the report template or PWA changed since the last release.
- [ ] `docs/audits/residual-risk.md` and `docs/RESPONSIBLE-TECH-AUDITS.md` §F are
      reviewed and re-dated.
- [ ] The N/A declarations (I18N, AI Evaluation) are re-confirmed honest, not just
      copy-pasted forward (DOC-14).
