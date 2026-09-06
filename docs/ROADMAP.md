# Olive's Bark Logger — Implementation Roadmap

> Generic enforcement lives in `/STANDARDS`. This document carries the decisions and project-specific values.
> **Last verified: 2026-05-31 · Recheck cadence: per recording-law review + audio-stack/hardware change.**

## 1. Snapshot
An on-device noise monitor that detects and logs barking/noise *events* — timestamps, durations, and sound levels — and generates an honest report, while never recording, storing, or transmitting audio. Primary target is a Raspberry Pi service; a browser PWA is a zero-hardware alternative. Built to provide objective data for a neighbor noise dispute.

## 2. Problem & users
- **Problem.** Vague noise complaints about Olive with no objective record on your side; recording the home would create legal/ethical problems and isn't necessary.
- **Primary user.** You (single-user, your apartment).
- **Jobs to be done.** "Log when it was actually loud, and for how long." · "Give me a clean report I can show property management." · "Do this without recording anyone."
- **Evidence basis.** A labeled test session (known barks/quiet) to validate event detection and thresholds.

## 3. Product definition
- **Vision.** Honest, level-only evidence of the real noise pattern — no audio, no exaggeration.
- **Scope (MoSCoW).**
  - *Must:* in-memory level computation (dBFS); event detection (threshold + min-duration + debounce); SQLite event log (no audio); report generator (charts + methodology + limitations); local-only operation.
  - *Should:* configurable quiet-hours ✅; calibration helper (offset toward approximate SPL) ✅; a small local dashboard ✅ (EXP-05: static, serverless `status.html`, see below).
  - *Could:* coarse on-device event tagging (bark-like vs ambient) computed from features without storing audio; CSV export.
  - *Won't (ever):* record/store/transmit audio; cloud upload; any claim the device can prove a sound's source.
- **Non-goals.** Not surveillance; not a recorder; not a courtroom-grade SPL meter.

## 4. Research & evidence
- **Recording-law basis.** Document why level-only + no-audio sidesteps two-party-consent/eavesdropping concerns; keep this front-and-center in design and report.
- **Acoustics.** Decide level metric (RMS → dBFS), the calibration-offset approach, and the device's stated limits (relative, not absolute, unless calibrated).
- **Detection validation.** Run a labeled session; tune threshold/duration/debounce; record false-positive/negative behavior.

## 5. Experience & design
- **Headless + report-first.** The monitor runs unattended; the deliverable is the report.
- **Report design.** Daily/hourly distributions, quiet-hours compliance, event counts, and a plain-language methodology + limitations section so it reads as honest, not adversarial.
- **Accessibility.** Reports/dashboard are keyboard-complete; every chart has a data-table equivalent; severity/levels not color-only. Release gate.

## 6. Architecture
- **Shape (Pi).** Python service using `sounddevice`/PortAudio: read frames → compute level in memory → event detector → SQLite (events only) → report generator (PDF/HTML + charts).
- **Shape (PWA alt).** Web Audio API `AnalyserNode` for levels, IndexedDB for events, same report generator logic; still audio-never-persisted.
- **Data model.** `Event(start, end, duration, peak_level, avg_level, [coarse_tag])`; `Calibration(offset, note)`. No audio fields exist anywhere.
- **Key decisions (ADRs).** Migrated on 2026-09-05 to numbered, append-only records under [`docs/adr/`](./adr/), which is now the source of truth for them: [0005](./adr/0005-level-only-no-audio-persisted.md) level-only, audio never persisted (rejected: recording — legal/ethical, and unnecessary) · [0006](./adr/0006-raspberry-pi-primary-pwa-alternative.md) Pi primary for reliable always-on, PWA as the no-hardware option · [0007](./adr/0007-in-memory-frames-discarded-immediately.md) in-memory processing with immediate discard (rejected: buffering raw audio to disk) · [0008](./adr/0008-mandatory-methodology-and-limitations.md) an honest methodology and limitations section, non-optionally (rejected: bare numbers with no limitations).

### ADRs added during build (M0–M4, 2026-06-05)

Recorded inline here until 2026-09-05, when GAP-DOC-1's migration gave each decision its
own numbered, append-only file under [`docs/adr/`](./adr/). Those files are the record;
what follows is an index, so the two cannot say different things. `tests/test_doc_figures.py`
fails the build if a migrated ADR is missing from it.

| ADR | Decision |
| --- | --- |
| [0009](./adr/0009-zero-dependency-pure-python-core.md) | Zero-dependency, pure-Python core; `live` and `pdf` are optional extras (rejected: numpy in the core) |
| [0010](./adr/0010-json-config-not-toml.md) | JSON config, not TOML — the 3.9 floor has no `tomllib` (rejected: a third-party TOML parser) |
| [0011](./adr/0011-hand-rendered-inline-svg-charts.md) | Hand-rendered inline-SVG charts with a paired data table, for byte-stable and accessible output (rejected: matplotlib) |
| [0012](./adr/0012-fixed-utc-offset-bucketing.md) | Fixed UTC-offset bucketing (`tz_offset_hours`) — **superseded by [0015](./adr/0015-dst-safe-iana-time-zones.md)**. This section stated it as live for months after the code stopped doing it |
| [0013](./adr/0013-structural-a11y-gate-as-the-floor.md) | Structural a11y gate as the enforced floor; pa11y/axe as a deeper layer, the screen-reader walkthrough human and review-gated |
| [0014](./adr/0014-type-check-under-310-semantics.md) | Type-check under 3.10 semantics on a 3.9 runtime floor, via `from __future__ import annotations` |

## 7. Quality attributes & metrics
| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Audio bytes written to disk or transmitted | 0 | no-audio test (asserts no audio write/IO path) | merge-blocking |
| Network egress in monitor | none | no-egress test | merge-blocking |
| Report includes methodology + limitations | always | report-content test | merge-blocking |
| Event-detection accuracy vs labeled session | meets stated threshold | eval test | review-gated |
| Report reproducibility (same log → same report) | deterministic | snapshot test | merge-blocking |
| axe violations (report/dashboard) | 0 | pa11y-ci | merge-blocking |
| Coverage | ≥ 85% / ≥ 80% | coverage | merge-blocking |

**Testing.** Unit (level math, detector thresholds/debounce, report assembly), integration (frame pipeline → event → log → report), eval (detection vs labeled session), a11y. A dedicated test proves no code path persists or transmits audio.

## 8. Implementation plan for Claude Code
```
monitor/   (capture, level compute, event detector)  [pi]
pwa/       (web-audio variant)                        [optional]
store/     (sqlite events, calibration)
report/    (charts + pdf/html + methodology)
docs/
```
- **M0 — Scaffold & gates.** ✅ Repo + CI (`/STANDARDS` gates + axe + the no-audio + no-egress tests). *Done: `make verify` green; no-audio test passes.*
- **M1 — Level pipeline.** ✅ In-memory RMS→dBFS with immediate frame discard. *Done: levels stream with zero audio persisted (test-proven).*
- **M2 — Event detection.** ✅ Threshold + min-duration + debounce → events to SQLite. *Done: labeled-session eval passes.*
- **M3 — Report generator.** ✅ Charts + distributions + quiet-hours + methodology/limitations. *Done: report renders with limitations; structural a11y gate green, pa11y in CI.*
- **M4 — Calibration + config.** ✅ `olive-calibrate` offset helper, `olive-tune` live meter, quiet-hours config. *Done: calibration stored + shown in report.*
- **M5 — PWA variant (optional).** ✅ Web Audio version (`pwa/`) sharing detection + report logic, IndexedDB, offline. *Done: events logged with audio never persisted; Node tests pass.*
- **M6 — Polish + validation.** ✅ Detection tuning, CSV/print export, property-based tests. *Done: all §7 gates pass and the eval threshold is met.*
- **Claude Code approach.** Build the no-audio guarantee first and design so there is literally no API to write audio; make the limitations section non-optional in the report.

### Productionization ADRs (P0–P2, 2026-06-05)

Migrated with the section above, on the same terms: the numbered files under
[`docs/adr/`](./adr/) are the record, and this is the index.

| ADR | Decision |
| --- | --- |
| [0015](./adr/0015-dst-safe-iana-time-zones.md) | DST-safe IANA zones via `zoneinfo` for bucketing and quiet hours, falling back to UTC without tzdata (supersedes [0012](./adr/0012-fixed-utc-offset-bucketing.md)) |
| [0016](./adr/0016-frame-coverage-accounting.md) | Count frames seen against frames dropped, and disclose coverage in "Measurement conditions" so silent backpressure cannot undercount events |
| [0017](./adr/0017-clock-integrity-guard.md) | `ClockGuard` records wall-vs-monotonic divergence past `clock_jump_tolerance_s` to `clock_anomalies` (schema v3) and the report discloses it (FIX-10) |
| [0018](./adr/0018-durability-and-lineage.md) | WAL with `synchronous=NORMAL`, a `user_version`-versioned schema with in-place migrations, a `sessions` table linking every event, config-driven retention (rejected: an ad-hoc schema with no upgrade path) |
| [0019](./adr/0019-detection-parameter-provenance.md) | Each session records the detection parameters its events were logged under (schema v3), and the report renders parameter epochs when they changed (FIX-02) |
| [0020](./adr/0020-unattended-ops.md) | Reconnecting `resilient_source`, an atomically-written file heartbeat, and a `systemd` unit hardened with `PrivateNetwork` / `ProtectSystem` |
| [0021](./adr/0021-time-driven-heartbeat-and-crash-safe-counters.md) | Heartbeat and frame counters flushed on a `checkpoint_interval_s` cadence, with no timer thread and no socket (FIX-04; rejected: an `sd_notify` socket watchdog) |
| [0022](./adr/0022-runtime-egress-proof.md) | A test booby-traps `socket` and runs the full pipeline and report, so no-egress is proved as behaviour and not only by a static import scan |
| [0023](./adr/0023-local-automation-hooks-over-af-unix.md) | Opt-in, emit-only heartbeat and event feed to a local `AF_UNIX` datagram socket, confined to `monitor/ipc.py` (EXP-11; rejected: an INET/localhost port) |
| [0024](./adr/0024-opt-in-coarse-event-tagging.md) | Coarse bark-like/ambient tagging from an in-memory zero-crossing-rate feature, opt-in and surfaced as a hedged hint; no audio stored |
| [0025](./adr/0025-bounded-per-event-envelope-stats.md) | Three seconds-valued envelope descriptors per event as O(1) running counters, carried through to SQLite v7 and the exports (EXP-02) |
| [0026](./adr/0026-pwa-as-a-parallel-implementation.md) | The PWA re-implements detector, level and report in JS with its own Node tests — a parallel implementation sharing semantics, not code |
| [0027](./adr/0027-pwa-epoch-clock-and-background-proof-capture.md) | `pwa/clock.js` anchors readings to epoch seconds; `setInterval` replaces `requestAnimationFrame`; `visibilitychange` records gaps the report discloses (FIX-05) |
| [0028](./adr/0028-cross-implementation-conformance-harness.md) | Language-neutral golden vectors in `spec/detector/` replayed by both ports to `1e-9`, with divergences and the change rule in [`spec/SEMANTICS.md`](../spec/SEMANTICS.md) (FIX-06) |
| [0029](./adr/0029-static-status-page-local-ops-console.md) | The ops console is an atomically-written static `status.html` from `report/status.py`, best-effort and a11y-floored (EXP-05; rejected: a live HTTP server) |

## 9. Community
Setup guide (Pi + PWA); a documented "why level-only" note others in similar disputes can reuse.

## 10. Legal & compliance
- **Recording law.** Level-only + no audio is the core compliance posture; documented in the report and README.
- **Honest use.** The report states methodology and limitations and never claims to attribute a sound to a specific source.
- **Privacy.** Local-only, minimal data, no audio.

## 11. Operations & sustainability
- **Hosting/cost.** A Raspberry Pi (or just a browser); no running cost; no cloud.
- **Maintenance.** Periodic recalibration; re-validate detection if the device moves.
- **Sustainability.** Self-contained and offline; nothing to keep paying for.

## 12. Responsible-tech summary
Top risks: (1) recording audio of the household or neighbors → never captured, stored, or transmitted (tested); (2) misleading evidence → mandatory methodology + limitations, no source-attribution claims; (3) any data leaving the device → local-only, no egress (tested); (4) inaccessible reports → full a11y with chart data-tables. Full treatment in [`RESPONSIBLE-TECH-AUDITS.md`](./RESPONSIBLE-TECH-AUDITS.md).
