# Olive's Bark Logger

**A privacy-first, on-device noise monitor that timestamps barking events and sound-level spikes and turns them into a clean report** — so the next time a downstairs neighbor complains, you have objective data instead of a he-said-she-said. It measures sound *levels* and event metadata only. It never records, stores, or transmits audio. By design, there is no recording to leak, subpoena, or wiretap.

**Status:** `Beta` · **Track:** Personal (on-device monitor + report generator) · **License:** MIT · **Data:** on-device/local
**Supported versions:** pre-1.0 — only the latest `0.y` release receives fixes; no LTS branch (REL-24).

## Why it matters
You've been on the receiving end of vague noise complaints about Olive with nothing concrete to point to. A small device that runs in your apartment and logs *when* sound crossed a threshold and for *how long* gives you an honest, time-stamped record — useful for property management or just for understanding the real pattern — without the legal and ethical problems of recording your home (or your neighbors).

## What it does
- **Listens for levels, not content:** computes sound level (dBFS, with a documented calibration offset) frame-by-frame in memory and discards the audio immediately.
- **Detects events:** threshold + minimum-duration + debounce → a "bark/noise event" with start, duration, and peak/average level.
- **Logs to SQLite:** events only — timestamps and levels, no audio.
- **Generates reports:** daily/hourly distributions, quiet-hours summaries, and event counts as a clean PDF/HTML with charts and a methodology + limitations section.
- **Runs on-device:** a Raspberry Pi service (primary) or a browser PWA (zero-hardware alternative), no network required.

## For Claude Code
- **Build entrypoint:** [`docs/ROADMAP.md`](./docs/ROADMAP.md) → *Implementation Plan*.
- **Hard guardrails:** **never write audio bytes to disk and never transmit audio anywhere** — raw frames are processed in memory and discarded; only derived levels + event metadata are persisted (this is the central design gate and has a merge-blocking test); the report must state its **methodology and limitations honestly** (uncalibrated dBFS is relative, not absolute SPL unless calibrated; the device cannot prove a sound's source); the tool runs **local-only** (no cloud, no telemetry); data is presented to inform, never fabricated or cherry-picked to manufacture a case.
- **Commands:** `make dev` · `make verify` · `make a11y` · `make report` · `make pwa-test`.

## Quickstart
```bash
make dev                       # create .venv and install (dev extras)
make verify                    # lint, type, coverage, security, a11y, PWA tests, i18n gate
make report                    # render report.html from a demo session (no hardware)
# Live capture on a Pi/laptop (optional audio dependency):
.venv/bin/pip install -e ".[live]"
.venv/bin/olive-tune     --config config.sample.json    # live meter; suggests a threshold
.venv/bin/olive-calibrate --config config.sample.json --reference-db 70   # store SPL offset
.venv/bin/olive-monitor  --config config.sample.json    # logs events; Ctrl-C to stop
.venv/bin/olive-report   --config config.sample.json --out report.html --csv events.csv
```
The core (level math, detector, store, report) has **zero runtime dependencies** and runs
on any Python 3.9+ with no installs; only live microphone capture needs the `live` extra.

> **Calibration is a single source of truth.** Events are stored as **raw** dBFS and the
> calibration offset is applied at report time from an append-only history owned by
> `olive-calibrate`. The `calibration_offset` / `calibration_note` fields in
> `config.sample.json` are **bootstrap-only (deprecated for steady-state use)**: they seed
> a database that has never been calibrated and are ignored once `olive-calibrate` has run.
> The monitor never writes calibration, so `olive-calibrate` followed by `olive-monitor`
> with a default config no longer reverts the device to uncalibrated.
> `threshold_dbfs` is defined against the same raw stored scale, so recalibrating never
> changes detection sensitivity. Render-time calibration is applied identically to the
> HTML report **and** to the `--csv` / `--violations-csv` / `--violations-html` exports;
> each CSV row records the offset included in its levels (`calibration_offset_db`).

## CLIs
| Command | What it does |
|---------|--------------|
| `olive-monitor` | Run the monitor: capture → level → detect → SQLite. Creates a capture *session* (lineage), writes a heartbeat file, reconnects on device failure, prunes per `retention_days`. |
| `olive-tune` | Show the live level so you can pick a threshold by ear; prints a suggestion. |
| `olive-calibrate` | Measure mean level against a reference SPL reading and append a calibration offset (with optional `--reference-instrument` provenance). This is the **only** writer of calibration; it is an append-only history applied at report time, so recalibrating never rewrites earlier events. |
| `olive-report` | Render the accessible HTML report (distributions + day×hour calendar heatmap + quiet-hours summary). Optional `--csv` event export, and `--violations-csv` / `--violations-html` for an honest quiet-hours report suitable for a neighbor/landlord/HOA submission. |

## Local status page
When `health_path` is configured, the monitor writes a static **`status.html`** next to
the heartbeat file on every check-in. You can instead enable only the page by setting
`status_path` explicitly. No server or network is involved. Open it straight from disk
(double-click, or `open status.html`) for an at-a-glance
ops view: heartbeat freshness (with a stale-heartbeat warning if the monitor has gone
quiet), the most recent level, frame coverage, recorded monitoring gaps, and a recent
summary (event count, minutes with events, busiest hour, quiet-hours totals). The page
is atomically rewritten, so you never catch it half-written, and it auto-refreshes every
60s if left open in a browser. It inherits the report's accessibility (keyboard-complete,
scoped table headers, reduced-motion) and the same no-audio guarantee.

## Deployment & variants
- **Raspberry Pi service:** `scripts/setup-pi.sh` installs PortAudio + a venv and the
  `deploy/olive-monitor.service` systemd unit (auto-restart, network-isolated, sandboxed).
- **Browser PWA (zero hardware):** [`pwa/`](./pwa/) — Web Audio levels, IndexedDB events,
  same no-audio guarantee, works offline. See [`pwa/README.md`](./pwa/README.md).
- **Container:** `Dockerfile` builds the report/analysis side for reproducible CI.

- **Definition of done:** the monitor runs unattended, logs noise events (levels + timestamps, zero audio) to local SQLite, and produces an honest, accessible report with charts and a stated methodology — all **applicable** `/STANDARDS` gates green (see Standards Conformance below) and the no-audio test passing. Full checklist: [`DEFINITION_OF_DONE.md`](./DEFINITION_OF_DONE.md).

## Observability
Tier C — OTel tracing out-of-scope (no network surface). Opt-in `--log-format json` is
not implemented yet (tracked: [`GAP-OBS-1`](./docs/GAP-LEDGER.md#gap-obs-1--observability---log-format-json-tier-c-structlog-reference-implementation));
today's surface is operator-facing `print()` lines plus a heartbeat JSON file
(`monitor/service.py`) with no secret/PII fields by design.

## Standards Conformance
Inherits [`/STANDARDS`](../STANDARDS/) (this table is the individual declaration DOC-11
requires; a bare "inherits" statement with no table is the exact silent-omission defect
the standard forbids — a prior version of this README made that mistake). `Applies —
gap tracked in GAP-NN` rows resolve to a real, dated, append-only entry in
[`docs/GAP-LEDGER.md`](./docs/GAP-LEDGER.md) (a GitHub issue was the original plan, but
this repo's tooling correctly refuses unsolicited issue creation as an external
write-effect, so gaps live here instead — see that file's header for why).

| Standard | State |
|----------|-------|
| Quality & Metrics | Applies — gap tracked in [GAP-QM-1](./docs/GAP-LEDGER.md#gap-qm-1--quality--metrics-dora-ledger--release-gate-checklist-execution) (DORA ledger; release-gate checklist exists in `DEFINITION_OF_DONE.md` but has never been run, since no release has happened) |
| Code Quality | Applies — gap tracked in [GAP-CQ-1](./docs/GAP-LEDGER.md#gap-cq-1--code-quality-python-floor-formal-adr-uvlockfile-pre-commit-hook-wiring-src-layout-hatchling) (Python-floor divergence recorded in [ADR-0002](./docs/adr/0002-python-39-floor.md); lockfile, hatchling, src/ layout still open) |
| Security & Supply-Chain | Applies — hardened posture (ASVS **L2**); gap tracked in [GAP-SEC-1](./docs/GAP-LEDGER.md#gap-sec-1--security--supply-chain-harden-runner-block-mode-codeql-lockfileosv-scanner-trufflehog-sbomsigning-scorecard) |
| CI/CD | Applies — gap tracked in [GAP-CICD-1](./docs/GAP-LEDGER.md#gap-cicd-1--cicd-apply-the-branch-ruleset-add-zizmor--codeql-actions) (ruleset committed at `.github/rulesets/main.json`, not yet applied — that's a live GitHub action for the maintainer, see the file's header) |
| Release & Versioning | Applies — release-producing deployed app; gap tracked in [GAP-REL-1](./docs/GAP-LEDGER.md#gap-rel-1--release--versioning-the-releasesupply-chain-pipeline-is-still-absent) (no release pipeline/tag yet; `CITATION.cff` intentionally carries no `date-released` until one exists) |
| Accessibility | Applies — gap tracked in [GAP-A11Y-1](./docs/GAP-LEDGER.md#gap-a11y-1--accessibility-scan-the-pwa-lighthouse-ci-regenerate-the-stale-walkthrough-acrvpat) (PWA surface unscanned; walkthrough stale since `8a9f1eb`) |
| Observability | Applies — Tier C: OTel out-of-scope (no network surface); `--log-format json` opt-in planned, gap tracked in [GAP-OBS-1](./docs/GAP-LEDGER.md#gap-obs-1--observability---log-format-json-tier-c-structlog-reference-implementation) |
| Internationalization | N/A — single-user tool, operator-only English output ([`docs/I18N.md`](./docs/I18N.md)) |
| AI Evaluation | N/A — no model/prompt/retrieval surface; nothing in this codebase calls an LLM SDK |
| Documentation | Applies — gap tracked in [GAP-DOC-1](./docs/GAP-LEDGER.md#gap-doc-1--documentation-vendor-standards-as-a-pinned-submodule-finish-the-adr-migration) (`/STANDARDS` vendoring blocked on a portfolio-level tag prerequisite; ADR migration in progress) |
| Responsible-Tech Framework | Applies — this repo's strongest standard: no-audio, no-egress, and honest-report-content are merge-blocking tests (`tests/test_no_audio.py`, `tests/test_no_egress.py`, `tests/test_report_content.py`); full treatment in [`docs/RESPONSIBLE-TECH-AUDITS.md`](./docs/RESPONSIBLE-TECH-AUDITS.md); gap tracked in [GAP-RTF-1](./docs/GAP-LEDGER.md#gap-rtf-1--responsible-tech-framework-per-section-sign-off-dates) (per-section sign-off dates) |

Last full audit: 2026-07-05 (`audit-2026-07-05/olive-bark-logger-AUDIT.md`,
33/138 controls PASS before that day's remediation pass; this table reflects the
post-remediation state and will drift from a fresh audit run — treat the audit file as
the point-in-time evidence trail, this table as the current claim).
