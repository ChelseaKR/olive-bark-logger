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
- **Generates reports:** daily/hourly distributions, quiet-hours summaries, and event counts as an accessible HTML report with charts and a methodology + limitations section. An optional, opt-in tagged PDF/A-3a export (`--pdf`, needs the `pdf` extra) is also available — see [Standards Conformance](#standards-conformance) for exactly what its accessibility claim does and does not cover.
- **Runs on-device:** a Raspberry Pi service (primary) or a browser PWA (zero-hardware alternative), no network required.

## Guardrails

Enforced by merge-blocking tests, not just promised:

- **No audio, ever.** Raw frames are processed in memory and discarded — audio bytes are
  never written to disk and never transmitted anywhere. Only derived levels and event
  metadata are persisted (this is the central design gate and has a merge-blocking test).
- **Local-only.** No cloud, no telemetry; the only optional output channel is the local,
  emit-only automation socket described below.
- **Honest reports.** Every report states its methodology and limitations — uncalibrated
  dBFS is relative, not absolute SPL unless calibrated, and the device cannot prove a
  sound's source. Data is presented to inform, never fabricated or cherry-picked to
  manufacture a case.
- **The caveats travel with every export.** The "what this can and cannot prove" cover
  block leads every artifact either implementation produces — HTML report, quiet-hours
  report, and both CSVs (as a `#` preamble, so the data rows still parse) — and anything
  reporting a quiet-hours count carries the line that a count is a measurement, not a
  determination. The strings live in [`spec/report/cover.json`](./spec/report/cover.json)
  and are replayed against Python *and* the browser edition; the gate discovers export
  paths from source, so a new one cannot ship without them.

Agent-facing build instructions live in [`CLAUDE.md`](./CLAUDE.md).

## Quickstart
```bash
make dev                       # create .venv and install (dev extras)
make verify                    # lint, type, coverage, security, a11y, PWA tests, i18n gate
make report                    # render report.html from a demo session (no hardware)
# Live capture on a Pi/laptop (optional audio dependency):
uv sync --locked --group dev --extra live
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
> each CSV row records the offset included in its levels (`calibration_offset_db`) and
> whether that offset was in force when the row was measured or back-applied from a
> calibration taken later (`calibration_basis`); the report states how many readings
> the first calibration postdates.

## CLIs
| Command | What it does |
|---------|--------------|
| `olive-monitor` | Run the monitor: capture → level → detect → SQLite. Creates a capture *session* (lineage), writes a heartbeat file, reconnects on device failure, prunes per `retention_days`. |
| `olive-tune` | Show the live level so you can pick a threshold by ear; prints a suggestion. |
| `olive-calibrate` | Measure mean level against a reference SPL reading and append a calibration offset (with optional `--reference-instrument` provenance). This is the **only** writer of calibration; it is an append-only history applied at report time, so recalibrating never rewrites earlier events. |
| `olive-report` | Render the accessible HTML report (distributions + day×hour calendar heatmap + quiet-hours summary). Optional `--csv` event export, `--violations-csv` / `--violations-html` for an honest quiet-hours report suitable for a neighbor/landlord/HOA submission, and `--pdf` / `--violations-pdf` for a tagged PDF/A-3a of either (needs the `pdf` extra; see [Standards Conformance](#standards-conformance)). |

> **Every quiet-hours export states how much of the window it observed.** Monitored vs
> wall-clock hours appear in the Summary block above the counts, each recorded monitoring
> gap is listed with its length, and every event row carries a `monitored` flag. Hours the
> device was not listening are reported as **not monitored, not quiet** — a count is only
> readable against the time it was counted over. That includes hours with **no monitor
> running at all**: those leave no gap row behind (writing one takes a running monitor),
> so coverage is measured against the capture-session ledger, and any stretch between one
> run ending and the next beginning is listed by date and subtracted. The figure is still
> an upper bound: an interruption *inside* a run that the monitor never got to record
> cannot appear in it, and the export says so. Where coverage cannot be determined from
> the record at all — including a log with no capture sessions, which cannot show off-air
> time in either direction — the export says that instead of leaving it out.

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

## Local automation hooks (opt-in, emit-only)
For home-automation *confounder context* — e.g. correlating a doorbell, robot vacuum, or
smart speaker with a logged spike — the monitor can emit its heartbeat and each event to a
**local** [`AF_UNIX`](https://en.wikipedia.org/wiki/Unix_domain_socket) datagram socket.
It is **off by default**, **one-way**, and **emit-only**: nothing is ever read back and no
network socket is opened, so the no-egress guarantee is unchanged (there is a merge-blocking
test that permits `socket` only in `monitor/ipc.py`, and only for `AF_UNIX`). Enable it with
`--ipc-socket /run/olive/ipc.sock` (or `"ipc_socket"` in the JSON config; `""` = disabled).
Sending is nonblocking and best-effort: if the listener is missing, stalled, or unable to
accept a datagram, that update is dropped instead of delaying sound capture.

A Home Assistant listener (same host) can pick up the JSON datagrams via a shell/command_line
sensor that reads the socket, e.g. with `socat`:

```yaml
# configuration.yaml — reads one JSON line per datagram from the local socket.
command_line:
  - sensor:
      name: Olive Bark Event
      command: "socat -u UNIX-RECV:/run/olive/ipc.sock,fork - "
      value_template: "{{ value_json.peak_level | default('idle') }}"
      json_attributes:
        - type
        - start
        - duration
        - peak_level
        - session_id
```

Payloads are `{"type": "event", "session_id", "start", "duration", "peak_level"}` per event
and the heartbeat health dict on each beat. Levels and metadata only — never audio.

## Deployment & variants
- **Raspberry Pi service:** `scripts/setup-pi.sh` installs PortAudio + a venv and the
  `deploy/olive-monitor.service` systemd unit (auto-restart, network-isolated, sandboxed).
- **Browser PWA (zero hardware):** [`pwa/`](./pwa/) — Web Audio levels, IndexedDB events,
  same no-audio guarantee, works offline. See [`pwa/README.md`](./pwa/README.md).
- **Container:** `Dockerfile` builds the report/analysis side for reproducible CI.

- **Definition of done:** the monitor runs unattended, logs noise events (levels + timestamps, zero audio) to local SQLite, and produces an honest, accessible report with charts and a stated methodology — all **applicable** `/STANDARDS` gates green (see Standards Conformance below) and the no-audio test passing. Full checklist: [`DEFINITION_OF_DONE.md`](./DEFINITION_OF_DONE.md).

## Observability
Tier C — OTel tracing out-of-scope (no network surface). Opt-in `--log-format json`
**ships** (`monitor/log.py`, `--log-format json` or `"log_format": "json"` in the config):
every operator line is emitted as one JSON object per line for a log shipper, using only
the standard library. `text` stays the default and is byte-for-byte the previous output.
See [`GAP-OBS-1`, addressed 2026-07-14](./docs/GAP-LEDGER.md#gap-obs-1--observability---log-format-json-tier-c-structlog-reference-implementation).
Alongside it: a heartbeat JSON file (`monitor/service.py`) with no secret/PII fields by
design.

## Standards Conformance
Inherits [`/STANDARDS`](../STANDARDS/) (this table is the individual declaration DOC-11
requires; a bare "inherits" statement with no table is the exact silent-omission defect
the standard forbids — a prior version of this README made that mistake). `Applies —
open gap recorded in GAP-NN` rows resolve to a real, dated, append-only entry in
[`docs/GAP-LEDGER.md`](./docs/GAP-LEDGER.md) (a GitHub issue was the original plan, but
this repo's tooling correctly refuses unsolicited issue creation as an external
write-effect, so gaps live here instead — see that file's header for why).

| Standard | State |
|----------|-------|
| Quality & Metrics | Applies — open gap recorded in [GAP-QM-1](./docs/GAP-LEDGER.md#gap-qm-1--quality--metrics-dora-ledger--release-gate-checklist-execution) (DORA ledger; release-gate checklist exists in `DEFINITION_OF_DONE.md` but has never been run, since no release has happened) |
| Code Quality | Applies — open gap recorded in [GAP-CQ-1](./docs/GAP-LEDGER.md#gap-cq-1--code-quality-python-floor-pre-commit-hook-wiring-src-layout-hatchling) (Python-floor divergence recorded in [ADR-0002](./docs/adr/0002-python-39-floor.md); pre-commit enforcement, hatchling, and `src/` layout still open) |
| Security & Supply-Chain | Applies — hardened posture (ASVS **L2**); open gap recorded in [GAP-SEC-1](./docs/GAP-LEDGER.md#gap-sec-1--security--supply-chain-harden-runner-block-mode-codeql-lockfileosv-scanner-trufflehog-sbomsigning-scorecard) |
| CI/CD | Applies — open gap recorded in [GAP-CICD-1](./docs/GAP-LEDGER.md#gap-cicd-1--cicd-reconcile-the-live-branch-ruleset-with-the-committed-one-add-zizmor--codeql-actions) (the live `protect-main` ruleset **matches** the committed `.github/rulesets/main.json` since the 2026-08-21 reconciliation — PR required, strict checks, no bypass actors, `required_signatures` deliberately dropped with a reasoned note, verified by `make ruleset-check` exit 0; still open: zizmor + CodeQL-actions) |
| Release & Versioning | Applies — release-producing deployed app; open gap recorded in [GAP-REL-1](./docs/GAP-LEDGER.md#gap-rel-1--release--versioning-the-releasesupply-chain-pipeline-is-still-absent) (tag-triggered `release.yml` now exists, REL-14 — no tag cut yet, and PyPI/GHCR/cosign are still open; `CITATION.cff` intentionally carries no `date-released` until a tag exists) |
| Accessibility | Applies — open gap recorded in [GAP-A11Y-1](./docs/GAP-LEDGER.md#gap-a11y-1--accessibility-lighthouse-ci-regenerate-the-stale-walkthrough-acrvpat-at-pass) (`pwa/index.html` **is** scanned by axe on every push and PR since 2026-07-11; still open: no Lighthouse, walkthrough stale since `8a9f1eb`, no ACR/VPAT, no NVDA or iOS VoiceOver pass) and [GAP-A11Y-2](./docs/GAP-LEDGER.md#gap-a11y-2--accessibility-tagged-pdfa-export-exp-06-has-no-human-at-walkthrough-or-verapdf-ci-gate) (the optional tagged PDF/A-3a export's structure is tested; its PDF/UA/"fully accessible" conformance is **not** verified — no human AT walkthrough has been done) |
| Observability | Applies — Tier C: OTel out-of-scope (no network surface); opt-in `--log-format json` **shipped** 2026-07-14 ([GAP-OBS-1: Addressed](./docs/GAP-LEDGER.md#gap-obs-1--observability---log-format-json-tier-c-structlog-reference-implementation)) |
| Internationalization | N/A — single-user tool, operator-only English output ([`docs/I18N.md`](./docs/I18N.md)) |
| AI Evaluation | N/A — no model/prompt/retrieval surface; nothing in this codebase calls an LLM SDK |
| Documentation | Applies — open gap recorded in [GAP-DOC-1](./docs/GAP-LEDGER.md#gap-doc-1--documentation-vendor-standards-as-a-pinned-submodule-finish-the-adr-migration) (`/STANDARDS` vendoring blocked on a portfolio-level tag prerequisite; ADR migration in progress) |
| Performance | Applies — the HTML report and the PWA are shipped human-facing surfaces, so this is in scope rather than exempt; no performance budget and no Lighthouse performance run are committed, recorded here as an open gap |
| Incident Response | Applies — [`SECURITY.md`](./SECURITY.md) is the private reporting channel and carries the acknowledgment and fix SLA; no severity-label convention and no postmortem template are committed, recorded here as an open gap |
| Data Governance | Applies — [`docs/audits/data-card.md`](./docs/audits/data-card.md) records the inventory, lineage, retention, and schema versioning; what is written is timestamps and levels only, with no audio persisted, held by the merge-blocking `tests/test_no_audio.py` |
| AI Development Measurement | Applies — no measurement artifact is committed in this repository, recorded here as an open gap |
| Responsible-Tech Framework | Applies — this repo's strongest standard: no-audio, no-egress, and honest-report-content are merge-blocking tests (`tests/test_no_audio.py`, `tests/test_no_egress.py`, `tests/test_report_content.py`); full treatment in [`docs/RESPONSIBLE-TECH-AUDITS.md`](./docs/RESPONSIBLE-TECH-AUDITS.md); open gap recorded in [GAP-RTF-1](./docs/GAP-LEDGER.md#gap-rtf-1--responsible-tech-framework-per-section-sign-off-dates) (per-section sign-off dates) |

Last full audit: 2026-07-05 (`audit-2026-07-05/olive-bark-logger-AUDIT.md`,
33/138 controls PASS before that day's remediation pass; this table reflects the
post-remediation state and will drift from a fresh audit run — treat the audit file as
the point-in-time evidence trail, this table as the current claim).

## Support

This is independent, unpaid work. If it has been useful to you, you can
<a href='https://ko-fi.com/T6T6GMYTU' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi6.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
