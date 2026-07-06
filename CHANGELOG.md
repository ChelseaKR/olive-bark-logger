# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[SemVer](https://semver.org/) once it makes its first tagged release.

**No version of this project has been tagged or released yet.** `pyproject.toml` and
`monitor/__init__.py` (via `importlib.metadata`) carry an in-development version number
(`0.1.0`) — that is a development milestone, not a release claim. Everything below lives
under `[Unreleased]` until a `git tag` actually exists; see `docs/GAP-LEDGER.md#gap-rel-1`
for the release-pipeline gap and `CITATION.cff` for the corrected (un-dated) citation
metadata. Do not add a dated `## [0.1.0] - YYYY-MM-DD` heading here until `v0.1.0` (or
whatever version supersedes it) is actually tagged — that was the exact "phantom
release" defect this file's absence let stand.

## [Unreleased]

### Added
- Calendar heatmap and quiet-hours violation CSV/HTML export in the report (day×hour
  grid, `--violations-csv` / `--violations-html`).
- MIT `LICENSE` and `CITATION.cff`.
- `i18n` N/A declaration and enforcement gate (`docs/I18N.md`, `make i18n`).
- Renovate-managed GitHub Actions digest pinning (`renovate.json`).
- STANDARDS conformance remediation pass (2026-07-05): README Standards Conformance
  table; `CODEOWNERS` + committed (not yet applied) branch ruleset; `make verify` now
  runs the security gate for real instead of soft-skipping; expanded ruff rule set
  (`W`, `S`, `C90`, `RUF`) and strict pytest flags; PEP 735 `[dependency-groups]`;
  derived `__version__` via `importlib.metadata`; `SECURITY.md`, `CONTRIBUTING.md`,
  `DEFINITION_OF_DONE.md`, `docs/adr/`, `docs/GAP-LEDGER.md`,
  `docs/a11y/STATEMENT.md`; digest-pinned + healthchecked `Dockerfile`; container CVE
  scan (Trivy) and `harden-runner` (audit mode) in CI.

### Fixed
- `on-device only, no cloud, no telemetry` guarantees unchanged and still merge-blocking
  (`tests/test_no_audio.py`, `tests/test_no_egress.py`) — this remediation pass
  deliberately did not touch those tests' assertions.
- Removed a hidden failure-swallowing bug in `Makefile`'s `security` target: the old
  `tool && run || echo "skipping"` pattern silently converted a **real** `pip-audit`
  finding into a "not installed, skipping" message whenever the tool actually was
  installed and found something. `make security` now fails loudly instead.

### Security
- GitHub Actions pinned to 40-character commit SHAs with Renovate digest-freshness
  automation (72h cooldown).
- `persist-credentials: false` on all checkout steps.

## Earlier history (pre-CHANGELOG, reconstructed from commit messages)
- Zero-dependency core (`monitor/`, `store/`, `report/`); no-audio and no-egress
  merge-blocking guarantees; accessible HTML report with methodology + limitations;
  Raspberry Pi systemd deployment; browser PWA variant; calibration and live-tuning
  CLIs; SQLite event store with WAL, schema versioning, and retention pruning.
