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
- **Key decisions (ADRs).** Level-only, audio-never-persisted (rejected: recording — legal/ethical, and unnecessary). Pi primary for reliable always-on (PWA as no-hardware option). In-memory processing with immediate discard (rejected: buffering raw audio to disk). Honest methodology section mandatory (rejected: bare numbers with no limitations).

### ADRs added during build (M0–M4, 2026-06-05)
- **Zero-dependency, pure-Python core.** Level math, detector, store, and report use only the standard library; `make verify` runs with no installs and only the optional `live` extra (`sounddevice`) is needed for real microphone capture. (Rejected: numpy in the core — unnecessary for RMS and adds a dependency to the always-run path.)
- **JSON config, not TOML.** Target runtime is Python 3.9, which lacks `tomllib`; config is JSON via the stdlib. (Rejected: a third-party TOML parser — avoid a dependency for config.)
- **Hand-rendered inline-SVG charts.** Charts are deterministic SVG with a paired data-table, so report output is byte-stable (snapshot-testable) and accessible without a plotting library. (Rejected: matplotlib — heavy, non-deterministic output, harder a11y.)
- **Fixed UTC-offset bucketing (`tz_offset_hours`).** A single-site monitor lives in one offset; bucketing against a fixed offset makes reports reproducible across machines. (Rejected: machine-local time — non-reproducible reports.)
- **Structural a11y gate as the enforced floor.** `tests/test_a11y.py` enforces the mechanically checkable WCAG subset everywhere (no browser needed); pa11y/axe runs as a deeper layer in `make a11y`/CI; the screen-reader walkthrough stays review-gated in `docs/audits/`.
- **Type-checking under 3.10 semantics.** Code targets 3.9 at runtime (via `from __future__ import annotations`) but is checked under mypy 3.10 (current mypy dropped 3.9 support); safe because annotations are not evaluated at runtime.

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
- **DST-safe time zones.** Bucketing and quiet hours use an IANA zone via `zoneinfo` (not a fixed offset), so they stay correct across daylight-saving changes. Falls back to UTC if tzdata is absent. (Rejected: fixed UTC offset — wrong half the year.)
- **Frame-coverage accounting.** The capture path counts frames seen vs dropped; the report's "Measurement conditions" discloses coverage so silent backpressure can't quietly undercount events. (Integrity complement to the no-audio guarantee.)
- **Clock-integrity guard (FIX-10). ✅ Done.** A `ClockGuard` tracks wall (`time.time`) vs monotonic (`time.monotonic`) time during capture; divergence beyond a configurable tolerance (`clock_jump_tolerance_s`, default 2 s) is persisted to a `clock_anomalies` table (schema v3) and disclosed in the report's "Measurement conditions" as a forward/backward jump with before/after wall times and delta — otherwise it states no anomalies. Important on RTC-less Pis where NTP sync lurches the clock and would silently smear event timestamps. Table is deliberately minimal and compatible with FIX-03's later gap table. (Integrity complement to frame-coverage accounting.)
- **Durability & lineage.** SQLite runs in WAL with `synchronous=NORMAL`; schema is versioned via `user_version` with in-place migrations; a `sessions` table records device/placement/calibration/tz + coverage and links each event for traceability. Retention pruning is config-driven. (Rejected: ad-hoc schema with no upgrade path.)
- **Detection-parameter provenance (FIX-02).** ✅ Each capture session records the threshold, min-duration, debounce, and sample-rate/frame-size in force when its events were logged (schema v3). The report sources the Methodology numbers from the session and, when settings changed across sessions, renders a "parameter epochs" table plus a disclosure that each event is described under the parameters active when it was logged. Legacy pre-v3 sessions read those columns back as `None` and fall back to config. *Done: migration + round-trip + two-session report tests pass.*
- **Unattended ops.** `resilient_source` reconnects on device failure with capped backoff; a heartbeat JSON file is written atomically for watchdogs; a hardened `systemd` unit (`PrivateNetwork`, `ProtectSystem`) enforces local-only at the OS level too.
- **Time-driven heartbeat & crash-safe counters (FIX-04, done 2026-07-02).** The heartbeat and the session frame counters are flushed on a wall-clock cadence (`checkpoint_interval_s`, default 30 s), not only on events and in the finally block. A `checkpointed(...)` generator piggybacks the periodic write on frame arrival (~10 Hz) with no timer thread and no sockets — the heartbeat stays file-based so the egress gate still holds — so a silent night keeps `updated_at` fresh and a power cut leaves the last-checkpointed `frames_seen`/`frames_dropped` on disk instead of losing the run. (Rejected: `sd_notify`/socket watchdog — would import a network module and trip the no-egress guardrail.)
- **Runtime egress proof.** In addition to the static import scan, a test booby-traps `socket` and runs the full pipeline + report to prove no network access at runtime.
- **EXP-11 — Local automation hooks over AF_UNIX (Home Assistant). ✅** Opt-in, emit-only one-way feed of the heartbeat and per-event dict to a local `AF_UNIX` datagram socket (`--ipc-socket` / `ipc_socket`, `""` = disabled), so a same-host home-automation listener can supply confounder context. Sends are nonblocking and best-effort so a stalled listener cannot freeze capture. All `socket` use is confined to `monitor/ipc.py` behind a surgical carve-out in the no-egress gate; canary tests prove the module opens only `AF_UNIX` (never `AF_INET`/`AF_INET6`) and the default path still opens no socket. Documented HA `command_line` example in the README. (Rejected: an INET/localhost port — that would be network egress.)
- **Coarse tagging (opt-in).** A cheap zero-crossing-rate feature, computed in memory and discarded, classifies events as bark-like/ambient; surfaced as a clearly-hedged "hint" in the report. No audio stored.
- **✅ Event anatomy (EXP-02) — bounded per-event envelope stats.** Each event stores three seconds-valued shape descriptors — rise time to threshold+6 dB, total time spent above +6 dB, and the longest unbroken loud run — so reports tell one long drone from hundreds of sharp barks. Computed as O(1) running counters over levels/timestamps (no audio, no buffering) and carried end to end (detector → SQLite v7 → CSV/violations exports). *Done: nullable columns migrate old rows to `None`; the no-audio gate lists the new fields deliberately.*
- **PWA parity.** The browser variant re-implements the detector/level/report in JS with its own Node tests; documented as a parallel implementation sharing semantics and the honest framing.
- **FIX-05 — PWA correctness: real timestamps and background-proof capture (done).** Events were stamped with `AudioContext.currentTime` (seconds since the context was created) while the report/CSV expect unix-epoch seconds; a `pwa/clock.js` anchor (`Date.now()/1000 − currentTime`) now maps every reading to epoch seconds via `toEpochSeconds`. The `requestAnimationFrame` sampling loop (throttled to ~0 Hz in a backgrounded tab) is replaced by a steady `setInterval` cleared on stop; `visibilitychange` records `{ kind: 'gap', start, end }` coverage holes for hidden/locked periods, which `summarize`/CSV exports exclude from event counts and the report surfaces as honest "monitoring gaps." Any in-progress detector event is flushed on stop. Covered by `pwa/clock.test.mjs`.
- **FIX-06 Cross-implementation conformance harness (Python ↔ PWA). ✅ Done.** `spec/detector/*.json` holds language-neutral golden vectors (threshold `>=` boundary, min-duration filtering, debounce bridging/splitting, flush-at-end, zero min-duration, peak/avg over loud readings only). Both `tests/test_conformance.py` (pytest, `monitor.detector.Detector`) and `pwa/conformance.test.mjs` (`node --test`, `pwa/detector.js`) replay the same vectors and assert equality to `1e-9`, so the two ports cannot drift silently. Intentional divergences (no `coarse_tag`/calibration/sessions in the PWA; CSV timezone divergence) and the rule "changing detection semantics means changing a vector on purpose" are documented in [`spec/SEMANTICS.md`](../spec/SEMANTICS.md), which also notes the quiet-hours/summarize extension point.
- **EXP-05 — Local ops console (static status page).** ✅ The monitor renders a static `status.html` (`report/status.py`) on each periodic check-in — latest level, heartbeat freshness, frame coverage, recorded monitoring gaps, and a recent summary. Written atomically (temp + `os.replace`), enabled from `health_path` or an explicit `status_path`, and best-effort so rendering can never stop capture. It reuses the report's structural-a11y floor and requires no server, network, or audio. (Rejected: a live HTTP server — a static file keeps the local-only, zero-egress guarantee.)

## 9. Go-to-market & community
- **Positioning.** "Honest, level-only noise evidence — no recording."
- **Marketing/comms.** A small, principled hardware/privacy project; a clean example of privacy-by-design under a real-world constraint.
- **Community.** Setup guide (Pi + PWA); a documented "why level-only" note others in similar disputes can reuse.

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
