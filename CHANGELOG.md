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

### Fixed
- **Two documents described gaps the code had already closed.** `README.md` called
  opt-in `--log-format json` "not implemented yet" and "planned" in two places; it
  shipped 2026-07-14 (`9a8dd4b`, #31) and the README was edited twice afterwards
  without catching it. `GAP-A11Y-1`'s headline clause said `pwa/index.html` was never
  scanned by pa11y/axe; CI has run `npx pa11y --runner axe ./pwa/index.html` on every
  push and PR since 2026-07-11 (`8858c45`, #17), in the required `verify` job. Both
  corrected, and the rest of GAP-A11Y-1 — no Lighthouse, stale walkthrough, no manual
  PWA pass, no ACR/VPAT, no NVDA/iOS VoiceOver — deliberately left open, because an
  automated scan is not a human walkthrough.
- `docs/a11y/STATEMENT.md`, the canonical accessibility declaration, carried the same
  stale "never scanned" claim in two places and is corrected with it.
- **The ledger is now readable by a test.** `tests/test_gap_ledger.py` pairs each
  closed-gap claim with the code fact that closed it (does `monitor/log.py` implement
  the JSON emitter; does `ci.yml` scan `pwa/index.html`) and fails when any document
  still describes it as open. Each check fires only while the capability is genuinely
  present, so removing a feature relaxes the check rather than breaking it.
- The quiet-hours violation report (`--violations-html`, `--violations-csv`, and the
  `--violations-pdf` rendered from the same HTML) now states **how much of the window
  the device actually monitored**, in the Summary block above the counts: monitored vs
  wall-clock hours, every recorded monitoring gap with its bounds and length, and the
  `monitored` flag per event row that until now only the CSV carried. Hours that were
  not monitored are reported as not monitored, not quiet. The figure is declared an
  upper bound (an interruption the monitor never recorded cannot appear in it), and a
  record that cannot support the figure at all says coverage could not be determined
  rather than omitting it. The document the README points at for a neighbor/landlord/HOA
  submission previously printed counts with nothing about the time they were counted
  over, so an outage during quiet hours read as a quiet night. Gated in
  `tests/test_report_content.py`, which now covers the violations renderer too.

- Release authorization now runs from reviewed `main` through the immutable
  portfolio authorizer, builds the exact verified commit, and hands only
  distributions, SBOM, and notes to a checkout-free publisher that rechecks
  the tag object.

### Added
- `--version` on all four CLI entrypoints (`olive-monitor`, `olive-report`,
  `olive-calibrate`, `olive-tune`), backed by the existing single-source-of-truth
  `monitor.__version__` (REL-02). Prints and exits before touching any config, device,
  or database, so it works even with no `--config` and no hardware attached.
- `--log-format json` (and a matching `log_format` config field) emits the
  monitor's operator lines as newline-delimited JSON for a log shipper, using
  only the standard library (`monitor/log.py`). `text` stays the default and is
  byte-for-byte the previous output. Implements GAP-OBS-1 / control OBS-22.

### Changed
- Development, CI, and tag verification now install from a committed `uv.lock` with
  `uv sync --locked`; `.python-version` preserves the accepted Python 3.9 device target,
  and the PDF-only dependencies carry explicit Python 3.10+ markers so the universal
  lock remains honest about that optional feature's runtime floor.

### Added
- Tag-triggered release workflow (`.github/workflows/release.yml`, REL-14, STANDARDS
  conformance remediation 2026-07-10): re-runs `make verify` at the tagged commit, then
  builds sdist + wheel, generates a CycloneDX SBOM, attests build provenance (keyless
  OIDC, no stored signing key), and publishes a GitHub Release with the matching
  `CHANGELOG.md` section as notes. Prepared ahead of the first tag — see the workflow
  file's header for what's deliberately still out of scope (PyPI, GHCR, cosign) and
  `docs/GAP-LEDGER.md#gap-rel-1` for the remaining release-pipeline gap.
- **EXP-06: optional tagged PDF/A-3a export** (`report/pdf_export.py`,
  `docs/adr/0004-weasyprint-for-tagged-pdf-a-export.md`). New `pdf` extra
  (`weasyprint>=67,<70`, needs Python >=3.10); new `--pdf` / `--violations-pdf` CLI
  flags on `olive-report`; `tests/test_pdf_export.py` verifies structural
  properties (tag tree, `/Lang`, heading order, table header association, chart
  descriptive text). **Not** a PDF/UA conformance claim — no human
  assistive-technology walkthrough has been performed yet (tracked:
  `docs/GAP-LEDGER.md#gap-a11y-2`).
- **Append-only calibration history (schema v3, FIX-01 / ADR-0003):**
  `calibration_history` table (`effective_from`, `offset`, `note`,
  `reference_instrument`); `olive-calibrate` is the only production writer and gains
  `--reference-instrument` provenance; the v2→v3 migration preserves a legacy
  calibration row as epoch 0. Reports spanning a recalibration disclose a per-epoch
  offsets table. A `schema_migrations` table records when each migration ran — the v3
  timestamp is the boundary between rows that may carry a baked-in offset and raw rows.
- CSV exports (`--csv`, `--violations-csv`) gain a per-row `calibration_offset_db`
  column recording the offset included in that row's levels (raw = value − offset); the
  violations HTML gains the same column and an honest multi-epoch calibration statement.
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
- **Calibration clobber (critical, data integrity; FIX-01 / ADR-0003):**
  `olive-monitor` no longer overwrites the stored calibration with the config value on
  every start (`olive-calibrate` → `olive-monitor` with a default config used to
  silently revert the device to uncalibrated). Event levels are now stored as **raw**
  dBFS and calibration is applied at render time from the append-only history —
  identically for the HTML report and the `--csv` / `--violations-csv` /
  `--violations-html` exports (exports previously emitted unadjusted levels, and the
  violations report's calibrated/uncalibrated statement came from the deprecated config
  field instead of the store). `config.calibration_offset` / `calibration_note` are
  bootstrap-only (deprecated); `threshold_dbfs` is defined against the raw stored
  scale. Legacy-data impact and recovery arithmetic: ADR-0003.
- `on-device only, no cloud, no telemetry` guarantees unchanged and still merge-blocking
  (`tests/test_no_audio.py`, `tests/test_no_egress.py`) — this remediation pass
  deliberately did not touch those tests' assertions.
- Removed a hidden failure-swallowing bug in `Makefile`'s `security` target: the old
  `tool && run || echo "skipping"` pattern silently converted a **real** `pip-audit`
  finding into a "not installed, skipping" message whenever the tool actually was
  installed and found something. `make security` now fails loudly instead.

### Security
- Dev toolchain: `pip` 26.1.2 -> 26.2.1 in `uv.lock` for PYSEC-2026-3721 (the
  Python >=3.10 resolution CI audits). The 3.9 resolution stays on 26.0.1 because
  26.2 dropped 3.9, so that ID and PYSEC-2026-3447 (`setuptools`, a venv seed package
  that is not a locked dependency) join the dated local-only waiver list in the
  `Makefile`, under the same "fix needs 3.10+" justification as the existing entries.
  Nothing here is shipped in the runtime, which has zero dependencies.
- GitHub Actions pinned to 40-character commit SHAs with Renovate digest-freshness
  automation (72h cooldown).
- `persist-credentials: false` on all checkout steps.

## Earlier history (pre-CHANGELOG, reconstructed from commit messages)
- Zero-dependency core (`monitor/`, `store/`, `report/`); no-audio and no-egress
  merge-blocking guarantees; accessible HTML report with methodology + limitations;
  Raspberry Pi systemd deployment; browser PWA variant; calibration and live-tuning
  CLIs; SQLite event store with WAL, schema versioning, and retention pruning.
