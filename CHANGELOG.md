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

### Changed
- **The live branch ruleset and the committed definition now match** (maintainer
  decision, 2026-08-21). Live `protect-main` was brought up to
  `.github/rulesets/main.json` for the `pull_request` rule (approvals 0 per ADR-0001,
  stale-review dismissal, thread resolution, code-owner routing), strict required
  status checks (stale branches cannot merge), and `bypass_actors: []` (the
  maintainer's former `pull_request` bypass is gone — no one merges past the checks).
  `main.json` was amended the other way for one rule: `required_signatures` is dropped
  with a reasoned note in `.github/rulesets/README.md` — commits here are routinely
  made by delegated agents without commit signing configured, so the rule would reject
  every push; release tags are signed elsewhere in the portfolio, and commit signing
  remains a separate future decision. The file also takes the live ruleset's name.
  `make ruleset-check` exits 0 against the live API, and
  `tests/test_ruleset_check.py` pins recorded before/after fixtures so both the
  historical divergence and the reconciled state stay tested offline.
- The README standards-conformance table now declares all fifteen standards.
  Performance, Incident Response, Data Governance, and AI Development
  Measurement were absent from it, so none of the four was recorded as met, as
  exempt, or as a gap. Performance, Incident Response, and AI Development
  Measurement are declared as applying with open gaps and no committed
  artifact; Data Governance points at the existing
  `docs/audits/data-card.md`.
- Rows that pointed at `docs/GAP-LEDGER.md` said "gap tracked in GAP-NN". The
  phrase reads as a reference to an issue tracker, and this repository
  deliberately keeps gaps in a committed ledger instead (the reason is in the
  paragraph above the table). Those rows now say "open gap recorded in
  GAP-NN", which is what the link actually resolves to. No gap changed state.

### Fixed
- **The status page claimed 100% frame coverage before the monitor had read a single
  frame.** `CaptureStats.coverage` (monitor/health.py) returns `1.0` — a reasonable
  "nothing dropped" identity — when no frames have been seen or dropped yet, and
  `monitor/service.py` publishes the very first heartbeat before the capture loop reads
  its first frame. Every run's first `status.html` therefore showed "Frame coverage:
  100.0%" for a device that had not yet been asked for one. The main report's
  measurement-conditions paragraph already guarded this correctly (it omits the
  coverage sentence entirely when no frames have been counted); the status page's Live
  Capture table did not. It now reads "not yet started, no frames processed yet" until
  at least one frame has been seen or dropped. Gated in `tests/test_status.py`.
- **Three more places where "no data" rendered as a confident value.** (1) A log with
  no events printed "Loudest peak: 0.0 dBFS" — digital full scale, the loudest reading
  the device can produce — in both the Python report and the browser edition; those
  figures now read "no events". (2) When monitoring coverage could not be computed, the
  main report printed nothing where the coverage sentence goes, which reads as "the
  whole window was observed"; it now says coverage could not be determined, the way the
  quiet-hours export already did. (3) The calendar heatmap had rows only for days that
  had events, so a quiet monitored day and a day the monitor was switched off both
  simply vanished from the calendar; every calendar day in the reporting window now has
  a row, so a quiet day shows its zeros and an off-air day is hatched "not monitored".
  Gated in `tests/test_absence_as_value.py` and `pwa/report.test.mjs`; the snapshot
  golden gains the explicit coverage note.
- **Readings the first calibration postdates are now disclosed as such.** A
  timestamp before the first calibration epoch resolves to that epoch by design (epoch
  0 covers all historical rows, ADR-0003), so one `olive-calibrate` run on day 20 was
  applied to events from day 1 with no marker anywhere: the report said "Calibrated.",
  the multi-epoch caveat never fired (one epoch), and every export row carried the same
  offset whether or not it was in force when the row was measured. The numbers are
  unchanged; every artifact now says it. The calibration banner and the methodology line
  name how many events (and ambient-ledger minutes) were recorded before the first
  calibration and when it was taken, on the single-offset and multi-epoch paths alike;
  the violations HTML carries the same statement; and every CSV row and the violations
  table carry a `calibration_basis` of `in-force` or `back-applied` (`bootstrap-config`
  / `none` without a history; `unstated` if a caller supplies offsets without a basis,
  rather than guessing). The migration's epoch 0 at `effective_from = 0` is not reported
  this way — it genuinely covers everything and keeps its own legacy caveat. Gated in
  `tests/test_calibration_disclosure.py` on the issue's exact fixture through the real
  CLI. (#50)
- **`retention_days` now reaches every table it should, and says what it reached.**
  Retention deleted rows from `events` and nothing else, so the opt-in ambient minute
  ledger (`minute_levels`, EXP-01) — the one *continuous* dataset in the store, 1,440
  rows a day while enabled — was kept forever, along with every gap, clock anomaly,
  and session row older than the horizon, while the operator line said "pruned N
  event(s)". `EventStore.prune` now returns per-table counts and prunes events, ambient
  minutes, gaps that ended before the horizon, clock anomalies, and sessions whose last
  vouched-for moment is before it and that no retained row references.
  `calibration_history` is exempt by design (a few operator-entered offsets needed to
  interpret what is kept); `store.RETENTION_EXEMPT_TABLES` states each exemption's
  reason and `tests/test_retention.py` enumerates the live schema against the two
  lists so a new table cannot sit outside the policy unnoticed. The operator line
  names every table's count (the JSON form carries `pruned_by_table`), and the data
  card documents retention per table. `Session.last_vouched_at` is the single rule
  for a session's end, shared by retention and the coverage arithmetic.
- **The caveats now travel with every export path, in both implementations.** The
  "what this can and cannot prove" cover block leads the browser edition's report HTML
  and both of its CSV downloads (`pwa/report.js`), and the Python event CSV
  (`--csv`), none of which carried it. The browser quiet-hours report also gains the
  no-verdict line ("being within quiet hours is not the same as a violation, and only
  the relevant authority can decide whether a rule was broken") and states that its
  readings are uncalibrated; its quiet-hours CSV preamble names the recorded monitoring
  gaps. In the CSVs the block is a leading `#` comment preamble, so the data rows below
  it still parse.
- The required strings are now one shared vector, `spec/report/cover.json`, replayed
  against both implementations (`tests/test_export_caveats.py`, `pwa/report.test.mjs`) —
  the same arrangement `spec/detector/*.json` uses for the two detectors, which is why
  the detectors never drifted and the report content did. The gate also *discovers*
  export paths from source and fails when the discovered set is not the checked set, so
  a new export path cannot ship without its caveats.
- **The docs now describe the branch ruleset that is actually live.** A ruleset
  (`protect-main`, id 18752850) has been active on `main` since 2026-07-09;
  `.github/rulesets/README.md`, the README's CI/CD row, and `GAP-CICD-1` all said it had
  never been applied, and that every merge-blocking gate in `ci.yml` was therefore
  "advisory only". They now state what is enforced (deletion, non-fast-forward, and
  eleven required checks — five of which are the always-green macOS twin, so the real
  strength is six) and enumerate the four ways the live ruleset is weaker than the
  committed `main.json`: `strict_required_status_checks_policy` false,
  `required_signatures` absent, the `pull_request` rule absent, and one bypass actor
  where the file says `[]`. The earlier changelog line describing a "committed (not yet
  applied) branch ruleset" was accurate when written and is superseded by this one.
- **The documented verification step can now see the live configuration.**
  `gh api .../rulesets --jq '.[] | select(.name=="main")'` selected on a name the live
  ruleset does not have, so it printed nothing and exited 0 — permanently reporting
  "not applied" whether or not a ruleset existed. Replaced by `make ruleset-check`
  (`scripts/check_ruleset.py`), which selects the ruleset covering `refs/heads/main` by
  target rather than name, prints every difference, and exits 1 on a difference or 2
  with `CANNOT VERIFY` when `gh` is missing, unauthenticated, or erroring. No path
  exits 0 without having read the live configuration. Not part of `make verify`, which
  may not assume network access or a `gh` token.
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
- **Monitoring coverage no longer counts time when no monitor was running.** The
  coverage figure was the reporting span minus the recorded gap ledger, and a gap row is
  only ever written by a *running* monitor catching its own audio-source failure
  (`resilient_source`, reason `device-error`). The most ordinary outage there is — the
  monitor simply not running, after a stop, a reboot, a crash, or a power cut — writes
  no gap row at all, so every hour of it was counted as monitored. A log of two runs
  with eight hours off air between them reported "the device monitored 9.5 of 9.5
  wall-clock hours (100%)", in green, in the document the README points at for a
  neighbor/landlord/HOA submission. Coverage is now derived from the capture-session
  ledger, which does record those hours as the hole between one session's end and the
  next one's start: the same log now reports 2.0 of 10.0 hours (20%), lists the off-air
  stretch with its bounds and length under a new "Time the monitor was not running"
  heading in both the HTML and the CSV preamble, and hatches those hours as *not
  monitored* in the calendar heatmap (a third state that was previously reachable only
  from a `device-error` gap). A log with no capture sessions at all cannot support the
  claim in either direction, so it keeps the old whole-span-minus-gaps figure and says
  in writing that it is the most generous reading the record allows. Also fixed in the
  same arithmetic: two *overlapping* recorded gaps were subtracted twice, understating
  coverage. Gated in `tests/test_report_content.py`.

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
- `--csv` and `--violations-csv` gain a `calibration_basis` column after
  `calibration_offset_db`; the violations HTML table gains the matching "Offset basis"
  column. Existing columns are unchanged and keep their order.
- `--csv` (`report/export.py`) and the browser CSV downloads now begin with the `#`
  cover preamble. Data rows are unchanged; readers that do not skip `#` comment lines
  need a one-line filter.
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
