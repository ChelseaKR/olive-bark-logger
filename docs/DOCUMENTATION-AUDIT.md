# Documentation Audit

Last reviewed: 2026-07-12. Base branch: `main`. **Counts corrected and put under a gate 2026-08-29.**

This audit records the documentation sweep and remediation loop for this repository. It checks the docs as a system: entry points, root-level process and legal files, project scope, setup and validation notes, safety and privacy posture, architecture and planning docs, local links, and the places where code, tests, workflows, and docs meet.

> **Correction (2026-08-29).** The counts in the Audit Results table below were typed by hand on 2026-07-12 and never re-read. "3 ADRs" was wrong when it was written — four already existed at this file's own commit (`8c00624`) — and by 2026-08-29 it was wrong by two. "33 Python/Node test files; 1 workflow file" had drifted to 48 and 3. "0 unresolved" links was a hand count over a tree that then grew three broken README anchors and a citation to a renamed ADR. The three figures below are now **derived from the tree by `tests/test_doc_figures.py`** and the link row is **enforced by `tests/test_doc_links.py`**, so this table fails a build rather than ageing quietly — the arrangement `docs/GAP-LEDGER.md` already uses for its own claims. They are live values, not as-of-the-review-date values; the "Last reviewed" stamp above governs the prose, not the numbers.

## Audit Results

| Area | Result | Evidence |
| --- | --- | --- |
| Entry docs | pass | `README.md` present |
| Security/process docs | pass | CONTRIBUTING.md, SECURITY.md, CHANGELOG.md |
| Architecture/planning docs | pass | 30 ADRs; canonical, research, and ideation roadmaps |
| Safety/privacy/audit docs | pass | 9 safety/privacy/accessibility/audit docs |
| Validation surface | pass | 51 Python/Node test files; 6 workflow files |
| Local doc links | pass | Every relative link, markdown anchor, and in-repo path citation checked on every run by `tests/test_doc_links.py`; 0 unresolved |

## Root-Level Documentation Audit

This section covers hand-authored documentation at the repository root and root-adjacent GitHub templates. It is separate from the `docs/` inventory so README, process, legal, release, and project-specific root files do not get hidden inside the larger docs tree.

| Surface | Result | Evidence |
| --- | --- | --- |
| Root README | pass | Present: `README.md` |
| Root process docs | pass | Present: `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` |
| Root legal, citation, and conduct docs | pass | Present: `LICENSE`, `NOTICE`, `CITATION.cff`, `CODE_OF_CONDUCT.md` |
| Other root project docs | info | `DEFINITION_OF_DONE.md` |
| Root-adjacent GitHub templates | pass | `.github/PULL_REQUEST_TEMPLATE.md`, `.github/CODEOWNERS` |
| Root/template doc links | pass | Checked on every run by `tests/test_doc_links.py`, which reads every tracked file rather than a hand-picked 24; 0 unresolved |

Root-level files checked:

- `CHANGELOG.md`
- `CITATION.cff`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `DEFINITION_OF_DONE.md`
- `LICENSE`
- `NOTICE`
- `README.md`
- `SECURITY.md`

Root-adjacent template files checked:

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/CODEOWNERS`

## Remediation In This PR

- Added missing root-level remediation docs found by the audit loop, including legal, conduct, contribution, or security files where absent.
- Added `docs/PROJECT-SCOPE.md` as the plain-language project and boundary map.
- Added this audit record so future doc changes have a dated baseline.
- Added or refreshed the docs index so scope, audit, and primary docs are easy to find.
- Fixed or added root/doc remediation files: `CODE_OF_CONDUCT.md`, `NOTICE`.

## Repo Surfaces Checked

Package and workspace metadata:

- Python package `olive-bark-logger` (>=3.9).

Source and operations surfaces seen at the repo root:

- `Dockerfile`
- `Makefile`
- `pyproject.toml`
- `scripts/`
- `tests/`

Workflow files checked:

- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/nightly.yml`
- `.github/workflows/release.yml`

## Documentation Inventory

| Category | Count | Representative files |
| --- | ---: | --- |
| architecture and interfaces | 30 | `docs/adr/0000-record-architecture-decisions.md`, `docs/adr/0001-single-maintainer-review-posture.md`, `docs/adr/0002-python-39-floor.md`, `docs/adr/0003-raw-levels-append-only-calibration.md`, `docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md`, plus the 25 records migrated out of `docs/ROADMAP.md` on 2026-09-05 (`0005`-`0029`) |
| entry points and repo process | 11 | `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/rulesets/README.md`, `CHANGELOG.md`, `CITATION.cff`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `LICENSE`, plus 3 more |
| other docs | 6 | `DEFINITION_OF_DONE.md`, `docs/GAP-LEDGER.md`, `docs/I18N.md`, `docs/PROJECT-SCOPE.md`, `docs/README.md`, `pwa/README.md` |
| planning and research | 8 | `docs/ROADMAP.md`, `docs/RESEARCH-ROADMAP.md`, `docs/USER-RESEARCH.md`, and 5 files under `docs/ideation/` |
| safety, privacy, accessibility, and audits | 9 | `docs/DOCUMENTATION-AUDIT.md`, `docs/RESPONSIBLE-TECH-AUDITS.md`, `docs/a11y/STATEMENT.md`, `docs/audits/accessibility-2026-06-05.md`, `docs/audits/data-card.md`, `docs/audits/methodology-and-limitations.md`, `docs/audits/no-audio-guarantee.md`, `docs/audits/recording-law-notes.md`, plus 1 more |

Full hand-authored doc inventory checked by this pass:

- `.github/CODEOWNERS`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/rulesets/README.md`
- `CHANGELOG.md`
- `CITATION.cff`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `DEFINITION_OF_DONE.md`
- `LICENSE`
- `NOTICE`
- `README.md`
- `SECURITY.md`
- `docs/DOCUMENTATION-AUDIT.md`
- `docs/GAP-LEDGER.md`
- `docs/I18N.md`
- `docs/PROJECT-SCOPE.md`
- `docs/README.md`
- `docs/RESPONSIBLE-TECH-AUDITS.md`
- `docs/RESEARCH-ROADMAP.md`
- `docs/ROADMAP.md`
- `docs/USER-RESEARCH.md`
- `docs/ideation/01-deep-dive.md`
- `docs/ideation/02-large-scale-fixes.md`
- `docs/ideation/03-expansions.md`
- `docs/ideation/04-impact-and-sequencing.md`
- `docs/ideation/README.md`
- `docs/a11y/STATEMENT.md`
- `docs/adr/0000-record-architecture-decisions.md`
- `docs/adr/0001-single-maintainer-review-posture.md`
- `docs/adr/0002-python-39-floor.md`
- `docs/adr/0003-raw-levels-append-only-calibration.md`
- `docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md`
- `docs/adr/0005-level-only-no-audio-persisted.md`
- `docs/adr/0006-raspberry-pi-primary-pwa-alternative.md`
- `docs/adr/0007-in-memory-frames-discarded-immediately.md`
- `docs/adr/0008-mandatory-methodology-and-limitations.md`
- `docs/adr/0009-zero-dependency-pure-python-core.md`
- `docs/adr/0010-json-config-not-toml.md`
- `docs/adr/0011-hand-rendered-inline-svg-charts.md`
- `docs/adr/0012-fixed-utc-offset-bucketing.md`
- `docs/adr/0013-structural-a11y-gate-as-the-floor.md`
- `docs/adr/0014-type-check-under-310-semantics.md`
- `docs/adr/0015-dst-safe-iana-time-zones.md`
- `docs/adr/0016-frame-coverage-accounting.md`
- `docs/adr/0017-clock-integrity-guard.md`
- `docs/adr/0018-durability-and-lineage.md`
- `docs/adr/0019-detection-parameter-provenance.md`
- `docs/adr/0020-unattended-ops.md`
- `docs/adr/0021-time-driven-heartbeat-and-crash-safe-counters.md`
- `docs/adr/0022-runtime-egress-proof.md`
- `docs/adr/0023-local-automation-hooks-over-af-unix.md`
- `docs/adr/0024-opt-in-coarse-event-tagging.md`
- `docs/adr/0025-bounded-per-event-envelope-stats.md`
- `docs/adr/0026-pwa-as-a-parallel-implementation.md`
- `docs/adr/0027-pwa-epoch-clock-and-background-proof-capture.md`
- `docs/adr/0028-cross-implementation-conformance-harness.md`
- `docs/adr/0029-static-status-page-local-ops-console.md`
- `docs/audits/accessibility-2026-06-05.md`
- `docs/audits/data-card.md`
- `docs/audits/methodology-and-limitations.md`
- `docs/audits/no-audio-guarantee.md`
- `docs/audits/recording-law-notes.md`
- `docs/audits/residual-risk.md`
- `pwa/README.md`
- `spec/SEMANTICS.md`

## Link Check

- Checked local links in authored Markdown and MDX docs after rebasing onto current `main`.
- Unresolved authored-doc links after remediation: 0.
- Root-level/template unresolved links after remediation: 0.

## Validation Notes

- The audit was generated from a clean worktree based on `origin/main` for this PR branch.
- Ran a local relative-link check over hand-authored Markdown and MDX docs.
- Ran an explicit root-level documentation presence and link check for README, process, legal, project, and template docs.
- Ran `git diff --check` across the PR worktrees after remediation.
- Product test suites remain the authority for runtime behavior; this PR changes documentation only.
