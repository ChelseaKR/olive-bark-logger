# Gap Ledger

**Last verified: 2026-07-05 · Recheck cadence: every remediation pass (see `docs/audits/`).**

This is the durable, in-repo tracking mechanism the README's
[Standards Conformance table](../README.md#standards-conformance) points to for every
`Applies — gap tracked in GAP-NN` row (DOC-13). A prior remediation pass attempted to
open GitHub issues for this instead; that write was correctly refused by the operator's
tooling (issue creation is an external, notification-triggering action outside this
session's scope), so gaps are tracked here — a real, dated, append-only file instead of
a fabricated issue number. **Rows are never deleted**, only marked `Closed <date>` in
place, so the history of what was known-open and when stays honest.

Source audit: `audit-2026-07-05/olive-bark-logger-AUDIT.md`. Source plan:
`audit-2026-07-05/olive-bark-logger-REMEDIATION.md` (P0/P1/P2/P3 item IDs below refer to
that document's section headers).

---

## GAP-QM-1 — Quality & Metrics: DORA ledger + release-gate checklist execution
**Status: Partially open (2026-07-05).** Controls: QM-11, QM-17.
- `DEFINITION_OF_DONE.md` (QM-18) and `.github/PULL_REQUEST_TEMPLATE.md` (QM-13,
  CQ-42) now exist (this pass), including a release checklist section.
- Still open: no deploy-frequency/lead-time/CFR/MTTR ledger exists yet (QM-11); the
  release-gate checklist has never actually been *run*, because no release has
  happened yet (QM-17 — 0.1.0 was stamped in `CITATION.cff` with no gate run and no
  tag; corrected this pass, see the Release & Versioning row).
Plan: REMEDIATION.md P2-3.

## GAP-CQ-1 — Code Quality: Python-floor formal ADR, uv/lockfile, pre-commit hook wiring, src/ layout, hatchling
**Status: Partially open (2026-07-05).** Controls: CQ-01, CQ-09, CQ-10, CQ-12 (mechanism
added, not yet wired to CI as a required gate), CQ-13/CQ-23, CQ-27 (closed this pass).
- `docs/adr/0002-python-39-floor.md` records the floor decision (option (b): keep 3.9,
  ADR on file) — this makes the *declaration* honest but the standard's floor is still
  ≥3.12, so this remains a tracked, accepted divergence, not a pass.
- No `uv.lock` / lockfile yet (CQ-09, SEC-13); Pi deploy still installs unpinned
  (`scripts/setup-pi.sh:19`, CQ-28).
- `.pre-commit-config.yaml` now exists (this pass) but is opt-in until a CI job asserts
  hooks are current, or until the ruleset in `.github/rulesets/main.json` is applied.
- Flat `monitor/`/`store`/`report/` layout, not `src/` (CQ-23) — no ADR yet either way.
- setuptools build backend, not hatchling (CQ-10).
Plan: REMEDIATION.md P1-3, P1-5, P2-4, P3.

## GAP-SEC-1 — Security & Supply-Chain: harden-runner block-mode, CodeQL, lockfile+osv-scanner, TruffleHog, SBOM+signing, Scorecard
**Status: Partially open (2026-07-05).** Controls: SEC-04 (audit-mode landed this pass,
block-mode still open), SEC-08, SEC-13, SEC-19, SEC-27, SEC-29, SEC-35..38.
- `step-security/harden-runner` now runs in `audit` mode on both CI jobs (this pass) —
  it logs egress instead of blocking it. Flipping to `egress-policy: block` needs one
  collected audit run to build the allow-list first (README Standards Conformance
  table, Security row).
- No CodeQL workflow, no scheduled TruffleHog full-history scan, no SBOM/signing (no
  release pipeline exists to attach them to — see Release & Versioning row), no
  OpenSSF Scorecard workflow/report.
Plan: REMEDIATION.md P1-2, P1-3, P1-4, P1-6, P2-1.

## GAP-CICD-1 — CI/CD: apply the branch ruleset, add zizmor + CodeQL-actions
**Status: Open (2026-07-05).** Controls: CICD-11, CICD-13, CICD-14, CICD-15, CICD-16,
CICD-19, CICD-20.
`.github/CODEOWNERS` and `.github/rulesets/main.json` are committed (this pass; see
P0-2 in the remediation plan), but the ruleset has not been **applied** — that's a live
GitHub UI/API action outside this session's scope (see README Standards Conformance
table, CI/CD row, for the exact command). No zizmor workflow-linter step; no CodeQL
`language: actions` workflow.
Plan: REMEDIATION.md P0-2 (activation step), P1-2, P1-6 (revisit required-check list
after these land).

## GAP-A11Y-1 — Accessibility: scan the PWA, Lighthouse CI, regenerate the stale walkthrough, ACR/VPAT
**Status: Open (2026-07-05).** Controls: A11Y-01/02/03/05/06 (PWA-surface half),
A11Y-11/12 (stale since `8a9f1eb`, 2026-06-29), A11Y-14, A11Y-18.
`pwa/index.html` is never scanned by pa11y/axe or Lighthouse; the committed manual
walkthrough (`docs/a11y/STATEMENT.md`, moved this pass from
`docs/audits/accessibility-2026-06-05.md`) predates the calendar-heatmap +
violations-export template change and has not been regenerated; no ACR/VPAT artifact
exists; no NVDA or iOS VoiceOver pass.
Plan: REMEDIATION.md P1-7, P2-2.

## GAP-REL-1 — Release & Versioning: the release/supply-chain pipeline is still absent
**Status: Partially open (2026-07-10).** Controls: REL-08, REL-13 (closed this pass),
REL-14 (closed this pass), REL-15, REL-16, REL-18 (digest pin + HEALTHCHECK closed
2026-07-05; GHCR publish still open), REL-20.
`.github/workflows/release.yml` now exists (STANDARDS conformance remediation
2026-07-10): tag-triggered on `v*`, re-runs `make verify` at the tagged commit, builds
sdist + wheel, generates a CycloneDX SBOM, attests build provenance via GitHub's native
keyless OIDC attestation, and publishes a GitHub Release with the matching CHANGELOG
section — all using only built-in `GITHUB_TOKEN`/OIDC, no external credentials. It has
never fired (no `v*` tag exists yet).
Still open, and still an explicit **L-effort, multi-day, externally-visible-action**
item not attempted in this pass: PyPI trusted-publisher configuration, a GHCR/registry
publish decision, and cosign key-based signing (provisioning/protecting a long-lived
signing key) — see the workflow file's own header for the enumerated list. See the
README Standards Conformance table's Release & Versioning row and `CITATION.cff`'s
in-file note for the corrected (un-released) version claim.
Plan: implement the PyPI/GHCR/cosign slice when ready to cut `v0.1.0` and a registry
decision has actually been made.

## GAP-DOC-1 — Documentation: vendor `/STANDARDS` as a pinned submodule, finish the ADR migration
**Status: Partially open (2026-07-05).** Controls: DOC-01, DOC-02, DOC-03, DOC-04
(scaffold landed this pass), DOC-05.
- `docs/adr/` now exists with a MADR-style template and two real ADRs
  (`0001-single-maintainer-review-posture.md`, `0002-python-39-floor.md`) — new
  expensive-to-reverse decisions get a numbered file from here forward. The 13
  decisions already embedded in `docs/ROADMAP.md` have **not** been mechanically
  migrated into individual files yet.
- DOC-01/02/03 (vendor `/STANDARDS` as a submodule pinned to a released tag, with CI
  asserting a non-`heads/` ref and `git diff --exit-code`) is blocked on a
  **portfolio-level prerequisite**: the `STANDARDS` repo has not published any version
  tags yet. This repo's README links `../STANDARDS/` as a sibling path, which only
  resolves inside the local portfolio checkout — that caveat stands until the
  standards repo itself is tagged and this repo can point a submodule at a tag instead
  of a branch head.
Plan: REMEDIATION.md P2-4.

## GAP-RTF-1 — Responsible-Tech Framework: per-section sign-off dates
**Status: Partially open (2026-07-05).** Controls: RTF-01, RTF-03, RTF-04.
`docs/RESPONSIBLE-TECH-AUDITS.md` now carries a document-level "Last verified /
Reviewer" stamp (this pass, DOC-15), and RTF-07's specific complaint (AI-evaluation
applicability never written down) is now resolved by the README's Standards
Conformance table. Still open: sections A (Ethics), B (Bias), and C (Privacy) don't
each carry their *own* dated sign-off line — only the document-level stamp exists.
RTF-08 (artifacts regenerated on every release) remains open; see GAP-A11Y-1 for the
concrete stale artifact.
Plan: REMEDIATION.md P2-3.

## GAP-OBS-1 — Observability: `--log-format json` (Tier C structlog reference implementation)
**Status: Open (2026-07-05).** Controls: OBS-22.
OBS §3 names this repo the portfolio's reference implementation for the Tier C
structlog JSON renderer; the monitor still only emits `print()` lines and one
heartbeat JSON blob. Not implemented this pass (M effort, touches the CLI surface and
needs its own tests) — tracked here rather than silently dropped.
Plan: REMEDIATION.md P2-5.

## GAP-A11Y-2 — Accessibility: tagged PDF/A export (EXP-06) has no human AT walkthrough or veraPDF CI gate
**Status: Open (2026-07-09).** Controls: A11Y-11/12 (PDF surface).
`report/pdf_export.py` (optional `pdf` extra, `docs/adr/0003-weasyprint-for-tagged-pdf-a-export.md`)
requests a tagged PDF/A-3a from WeasyPrint and `tests/test_pdf_export.py` verifies the
structural properties a test suite can check (tag tree present, `/Lang`/`/MarkInfo`,
heading order, table header association, chart-summary text survival). What is
**not** done, same as `docs/ideation/04-impact-and-sequencing.md`'s human-gate table
already named for this item:
1. **No human assistive-technology walkthrough.** No PDF/UA or "fully accessible"
   conformance claim is made anywhere in this repo, and none should be made until a
   real screen-reader pass is performed and committed, the same way
   `docs/audits/accessibility-2026-06-05.md` documents the HTML report's walkthrough.
2. **No veraPDF CI gate.** `make pdf-a11y` runs veraPDF locally, best-effort, when
   installed (a Java tool, not on PyPI); it is not wired into CI and is not
   merge-blocking.
Plan: none yet — first requires an available AT reviewer (human gate), not a backlog
item to schedule unilaterally.
