# Project Scope

Last reviewed: 2026-07-12. Base branch: `main`.

This file is a plain-language map of the project as it exists on `main`. It does not replace the README, roadmap, audit docs, or source comments. It points to them so a reviewer can see the whole shape without reading every file first.

## What This Project Is

Olive's Bark Logger is an on-device noise monitor and report generator. It measures sound levels and event timing, stores only derived event data, and produces reports without recording audio.

Package metadata checked in this pass:

- Python package `olive-bark-logger` for Python `>=3.9`.

## Who It Serves

- People who need a factual log of barking or noise patterns in their home.
- Maintainers building privacy-preserving measurement tools.
- Reviewers checking that no audio is stored, transmitted, or implied by the reports.

## What It Covers

- Level calculation, event detection, SQLite storage, report rendering, and quiet-hours summaries.
- A Raspberry Pi service path and a browser PWA variant.
- Calibration and tuning CLIs.
- Docs for methodology, gaps, audits, ADRs, PWA use, and deployment.
- Tests for no-audio behavior, no egress, reporting, detector logic, and PWA code.

## How It Is Put Together

- monitor/ contains capture, level, detector, health, config, and service code.
- report/ contains charts, aggregation, export, and rendering.
- store/ contains the SQLite layer.
- pwa/ holds the browser variant.
- docs/ records audits, gaps, ADRs, methodology, and limitations.

Observed source and operations surfaces:

- `Dockerfile`
- `Makefile`
- `deploy/`
- `monitor/`
- `pwa/`
- `pyproject.toml`
- `report/`
- `scripts/`
- `store/`

GitHub workflow files checked:

- `.github/workflows/ci.yml`

## Trust Boundaries

- The central guarantee is no audio bytes written to disk or sent out.
- Reports state limits: uncalibrated dBFS is relative, and the tool cannot prove what made a sound.
- Local-only operation reduces disclosure risk, but users still control where exported reports go.

## Outside This Scope

- It is not a surveillance device.
- It cannot identify a sound source with certainty.
- It does not make legal or lease-compliance conclusions.

## Docs And Evidence Checked

This pass checked 37 hand-authored doc or metadata files, 33 Python/Node test files, and 1 workflow file on `main`. The count excludes vendored provider licenses, dependency folders, generated cache files, and generated artifacts.

Primary docs checked:

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/rulesets/README.md`
- `CHANGELOG.md`
- `CITATION.cff`
- `CONTRIBUTING.md`
- `DEFINITION_OF_DONE.md`
- `LICENSE`
- `README.md`
- `SECURITY.md`
- `docs/GAP-LEDGER.md`
- `docs/I18N.md`
- `docs/RESPONSIBLE-TECH-AUDITS.md`
- `docs/RESEARCH-ROADMAP.md`
- `docs/ROADMAP.md`
- `docs/USER-RESEARCH.md`
- `docs/ideation/README.md`
- `docs/a11y/STATEMENT.md`
- `docs/adr/0000-record-architecture-decisions.md`
- `docs/adr/0001-single-maintainer-review-posture.md`
- `docs/adr/0002-python-39-floor.md`
- `docs/audits/accessibility-2026-06-05.md`
- `docs/audits/data-card.md`
- `docs/audits/methodology-and-limitations.md`
- `docs/audits/no-audio-guarantee.md`
- `docs/audits/recording-law-notes.md`
- `docs/audits/residual-risk.md`
- `pwa/README.md`
- `spec/SEMANTICS.md`

Representative test files checked:

- `pwa/detector.test.mjs`
- `pwa/report.test.mjs`
- `tests/conftest.py`
- `tests/snapshots/report.html`
- `tests/test_a11y.py`
- `tests/test_aggregate.py`
- `tests/test_calibrate.py`
- `tests/test_capture_resilient.py`
- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_detector.py`
- `tests/test_eval.py`
- `tests/test_export.py`
- `tests/test_features.py`
- `tests/test_health.py`
- `tests/test_heatmap.py`
- `tests/test_integration.py`
- `tests/test_level.py`
- `tests/test_no_audio.py`
- `tests/test_no_egress.py`
- `tests/test_properties.py`
- `tests/test_report_content.py`
- `tests/test_report_snapshot.py`
- `tests/test_store_durability.py`
- `tests/test_violations.py`

## Validation Notes

For this docs PR, validation means the scope file was generated from the clean `origin/main` worktree, reviewed against repo metadata and docs inventory, and checked with `git diff --check`. Project test suites are still the authority for code behavior, because this PR changes documentation only.
