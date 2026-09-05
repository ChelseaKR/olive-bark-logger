# Gap Ledger

**Last verified: 2026-09-05 · Recheck cadence: every remediation pass (see `docs/audits/`).**

> The stamp above read `2026-08-15` until 2026-08-29, while entries below carried updates
> dated 2026-08-21, 2026-08-26 and 2026-08-27 — three remediation passes edited this file
> without moving its own freshness date, which is the ledger committing the exact defect it
> exists to catch. It is now set to the newest date any entry records, and
> `tests/test_doc_figures.py` fails the build if it ever falls behind again.

> An entry that describes a gap the code has since closed is as wrong as one that hides a
> gap — gentler, but the same defect: a document about the code that stopped tracking the
> code. `tests/test_gap_ledger.py` reads this file and the README against a small set of
> code facts, so a stale entry fails a build rather than ageing quietly. Add an assertion
> there whenever an entry here makes a claim a test could check.

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

## GAP-CQ-1 — Code Quality: Python floor, pre-commit hook wiring, src/ layout, hatchling
**Status: Partially open (updated 2026-07-14).** Controls: CQ-01, CQ-10, CQ-12 (mechanism
added, not yet wired to CI as a required gate), CQ-13/CQ-23, CQ-27 (closed this pass).
- `docs/adr/0002-python-39-floor.md` records the floor decision (option (b): keep 3.9,
  ADR on file) — this makes the *declaration* honest but the standard's floor is still
  ≥3.12, so this remains a tracked, accepted divergence, not a pass.
- `uv.lock` and `.python-version` now make development, CI, and tag verification
  reproducible (CQ-09, SEC-13). The Pi deploy remains source-based because the runtime
  has zero mandatory dependencies; pinning the optional live-capture stack is still
  tracked under CQ-28 (`scripts/setup-pi.sh:19`).
- `.pre-commit-config.yaml` now exists (this pass) but is opt-in until a CI job asserts
  hooks are current, or until the ruleset in `.github/rulesets/main.json` is applied.
- Flat `monitor/`/`store`/`report/` layout, not `src/` (CQ-23) — no ADR yet either way.
- setuptools build backend, not hatchling (CQ-10).
Plan: REMEDIATION.md P1-3, P1-5, P2-4, P3.

## GAP-SEC-1 — Security & Supply-Chain: harden-runner block-mode, CodeQL, osv-scanner, TruffleHog, SBOM+signing, Scorecard
**Status: Partially open (updated 2026-07-14).** Controls: SEC-04 (audit-mode landed,
block-mode still open), SEC-08, SEC-19, SEC-27, SEC-29, SEC-35..38.
- `step-security/harden-runner` now runs in `audit` mode on both CI jobs (this pass) —
  it logs egress instead of blocking it. Flipping to `egress-policy: block` needs one
  collected audit run to build the allow-list first (README Standards Conformance
  table, Security row).
- No CodeQL workflow, no scheduled TruffleHog full-history scan, no SBOM/signing (no
  release pipeline exists to attach them to — see Release & Versioning row), no
  OpenSSF Scorecard workflow/report.
Plan: REMEDIATION.md P1-2, P1-3, P1-4, P1-6, P2-1.

## GAP-CICD-1 — CI/CD: reconcile the live branch ruleset with the committed one, add zizmor + CodeQL-actions
**Status: Partially open (updated 2026-08-15).** Controls: CICD-11, CICD-13, CICD-14,
CICD-15, CICD-16, CICD-19, CICD-20.

Correction to this entry as written on 2026-07-05: it said the ruleset "has not been
**applied**". **A ruleset has been active on `main` since 2026-07-09** — `protect-main`
(id 18752850, `enforcement: active`). This entry, `.github/rulesets/README.md`, and the
README's CI/CD row all kept saying otherwise for over a month, while `ci.yml`'s
`test-matrix-macos-nightly-notice` job existed precisely because the ruleset *is* live.
The stated way to confirm it (`--jq '.[] | select(.name=="main")'`) selected on a name
the live ruleset does not have, printed nothing, and exited 0 — so the check could only
ever return "not applied". Replaced by `make ruleset-check`
(`scripts/check_ruleset.py`), which selects by target rather than name, prints every
difference, and exits 2 with `CANNOT VERIFY` rather than 0 when it cannot read the live
configuration.

**Enforced today (2026-08-26):** deletion, non-fast-forward, a required pull request,
and **six** required status checks — `verify` and five `test-matrix (ubuntu-latest, X)`
legs. Count and strength are now the same number.

Update 2026-08-26: **five of the eleven required checks could not fail, and are gone.**
`test-matrix (macos-latest, 3.9–3.13)` were required to merge and were reported by
`test-matrix-macos-nightly-notice`, a job that renamed itself to those five context names
and ran one `echo`. The live API, read that day for `ci.yml` run 32648677865 on `main`:
`labels: ["ubuntu-latest"]`, steps `["Set up job", "Run echo …", "Complete job"]`, four
seconds, `conclusion: success`. The previous version of this entry conceded the point in
prose ("the real strength is six") and left the fake checks required, which is the whole
lesson: a documented placeholder gate is still a placeholder gate.

The five contexts were removed from `main.json` and from the live ruleset, and the notice
job was deleted. **No stand-in replaced it.** CI-CD-STANDARD §11b forbids `macos-*` on
PR CI, so two checks that read real results were added *inside* the already-required
`verify` job instead — no new required context name, because adding one is how this got
in:

- `scripts/check_nightly_macos.py` (`make nightly-check`) fails unless the nightly macOS
  sweep ran on `main`, on runners the API labels `macos-*`, within 7 days, and passed.
- `scripts/check_ruleset.py --scope public` fails unless the live ruleset still matches
  `main.json`. That check existed, was correct, and ran nowhere; a PR rewriting the
  committed ruleset merged green.

Two limits, recorded rather than glossed: the macOS gate is **lagging** (a macOS-only
regression merges, and blocks every merge after the next nightly catches it — nothing
respecting §11b can do better), and CI's ruleset check runs `--scope public` because the
Actions `GITHUB_TOKEN` cannot read repository administration, so **it does not check
bypass actors**; `make ruleset-check` with a maintainer token is the only thing that
does. A related defect was fixed in the same pass: `.get("bypass_actors", [])` had been
reading the reduced payload's *absent* field as "[] — no one bypasses".

Update 2026-08-21: **the ruleset divergence is closed.** The live `protect-main` was
brought up to `main.json` for the `pull_request` rule (approvals 0 per ADR-0001),
`strict_required_status_checks_policy: true`, and `bypass_actors: []` (the maintainer's
former `pull_request` bypass is gone); `main.json` was amended to drop
`required_signatures` as a decision (delegated agents commit unsigned; release tags are
signed elsewhere in the portfolio; commit signing is a separate future decision — see
`.github/rulesets/README.md`) and to carry the live name. `make ruleset-check` exits 0
against the live API, and `tests/test_ruleset_check.py` pins a recorded copy of the
reconciled live ruleset.

Update 2026-08-27: **`bypass_actors: []` was false, and had been since the
portfolio-wide administrator bypass was added.** `make ruleset-check` reported it in one
line -- `bypass_actors: committed [] (no one bypasses), live ['RepositoryRole:5
(always)']` -- and the same API read returned `"current_user_can_bypass": "always"` for
the maintainer's token. `main.json`, `.github/rulesets/README.md` ("No bypass actors. No
one -- including the repository owner -- merges past these rules") and this repository's
README all described a stricter gate than the one in force. The bypass is deliberate and
is not being removed: the owner requires a recovery path in every repository in this
portfolio. **The file was amended to reality, not the ruleset to the file**, and
`tests/test_ruleset_check.py` now fails if the committed definition stops recording it or
if the live ruleset loses it.

The part of this worth carrying forward: the one field that turned out to be wrong is the
one field CI structurally cannot read. `verify` runs `--scope public`, and the publicly
readable ruleset payload omits `bypass_actors`; every other field is diffed on every pull
request. `--scope public` says so on its own passing path, and `make ruleset-check` with a
maintainer token remains the only check on bypass actors. That is a stated limit, not a
gap to close -- GitHub does not offer workflows the `administration` permission.

Update 2026-08-28: **the check compared the bypass list by equality, which is the one
comparison that cannot catch a lockout.** If `main.json` were ever "tidied" back to
`"bypass_actors": []` on a day the owner had also been locked out, the two sides would
agree and `check_ruleset.py` would have reported a match on precisely the incident the
field protects. `bypass_findings` now holds the live ruleset and the committed file
against the owner's standing bypass **independently**, and compares only *other* actors
between them, so a second bypass granted to a team, an app or another role is still a
finding in either direction. This matters here more than elsewhere because
`.github/rulesets/README.md` publishes a `--method PUT --input .github/rulesets/main.json`
reapply procedure: following it while the file said `[]` would itself have caused the
lockout, so the file is now checked as a thing that will be applied, not only as a
description of what is live.

**Closed 2026-09-05: both static-analysis halves.**
- **zizmor** runs over `.github/workflows/` as `make workflows`, and CI runs the same
  command as step 2c *inside* the already-required `verify` job. Deliberately not a new
  required context: the 2026-08-26 entry above is about five required checks that could
  not fail, and the lesson recorded then was that adding a context name is how such a
  check gets in. Clean today, with 9 findings suppressed by `# zizmor: ignore[rule]`
  comments that carry their reason on the same line.
- **CodeQL `language: actions`** is `.github/workflows/codeql.yml`. This one cannot live
  inside `verify`: it uploads SARIF to code scanning, which needs its own workflow and
  `security-events: write`. So it *is* a new context, and the required-check list has to
  be revisited deliberately rather than inherited by accident. Python analysis is
  deliberately not enabled yet: the runtime core is stdlib-only, so the workflow surface
  is where an injected expression or an unpinned action would actually reach a token, and
  adding `python` later is one matrix entry.

**Still open:**
- The required-check list has not been revisited to decide whether `codeql (actions)`
  should be required (REMEDIATION.md P1-6).

Plan: REMEDIATION.md P0-2 (now a reconciliation, not an activation), P1-2, P1-6
(revisit required-check list after these land).

## GAP-A11Y-1 — Accessibility: Lighthouse CI, regenerate the stale walkthrough, ACR/VPAT, AT pass
**Status: Partially open (updated 2026-08-15).** Controls: A11Y-01/02/03/05/06 (PWA-surface
half — automated scan **closed**, manual pass still open), A11Y-11/12 (stale since
`8a9f1eb`, 2026-06-29), A11Y-14, A11Y-18.

Correction to this entry as written on 2026-07-05: its opening sentence claimed the PWA
page had no pa11y/axe or Lighthouse coverage at all. **The axe half closed on
2026-07-11** (`8858c45`, #17): `.github/workflows/ci.yml:113–116` runs
`npx pa11y --runner axe ./pwa/index.html` on every push and pull request, in the `verify`
job, which is a required status check. That was six days after this entry was written and
it stayed stale for a month; the clause that reads as the headline was the wrong one.

Still open, unchanged:
- **No Lighthouse CI accessibility score** for either surface.
- **The manual walkthrough is stale.** `docs/a11y/STATEMENT.md` (moved this pass from
  `docs/audits/accessibility-2026-06-05.md`) predates the calendar-heatmap +
  violations-export template change and has not been regenerated.
- **No manual pass on the PWA surface** — keyboard / screen-reader / zoom / reflow. The
  axe scan is automated coverage, which is not the same claim.
- **No ACR/VPAT artifact.**
- **No NVDA+Firefox/Chrome or iOS VoiceOver pass** (VoiceOver/macOS only, on the report).
- **No target-size (WCAG 2.5.8) check** for the PWA's real buttons and inputs.

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

## GAP-OBS-1 — Observability: `--log-format json`
**Status: Addressed (2026-07-14).** Controls: OBS-22.
The monitor supports `--log-format json` (and a `log_format` config field): its
operator lines are emitted as newline-delimited JSON through `monitor/log.py`,
with `text` the byte-for-byte default. OBS §3 framed this as the Tier C structlog
renderer; it is instead implemented with the standard library only, honoring the
zero-dependency runtime-core ADR — an equivalent stdlib JSON renderer rather than
a new dependency. The interactive `olive-calibrate` meter stays plain text (a live
TTY UI, not operator logging).
Plan: REMEDIATION.md P2-5.

## GAP-A11Y-2 — Accessibility: tagged PDF/A export (EXP-06) has no human AT walkthrough or veraPDF CI gate
**Status: Open (2026-07-09).** Controls: A11Y-11/12 (PDF surface).
`report/pdf_export.py` (optional `pdf` extra, `docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md`)
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
