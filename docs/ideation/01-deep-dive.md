# Deep Dive — Current State (2026-07-01)

Assessment from a full read of source, tests, CI, deployment config, and audit docs on
`main` (`645b6b2`) plus the unmerged `research-panel-and-roadmap` branch (`0f98ce0`).
Nothing was executed; test suites and builds were not run.

## Architecture as actually built

The repo is a small, disciplined, zero-runtime-dependency Python core with a parallel
browser implementation:

- **Capture** — `monitor/capture.py` (synthetic labeled source + `resilient_source`
  reconnect wrapper with capped exponential backoff), `monitor/capture_live.py`
  (`sounddevice` callback → bounded in-memory queue, drops counted under backpressure;
  lazily imported so the core stays dependency-free, per `pyproject.toml`'s `[live]`
  extra).
- **Level math** — `monitor/level.py`: per-frame RMS → dBFS, clamped at a −120 dBFS
  silence floor; calibration offset added here, meaning **stored event levels have the
  offset baked in**.
- **Detection** — `monitor/detector.py`: a clean threshold/min-duration/debounce state
  machine emitting a frozen six-field `Event`; ported faithfully to `pwa/detector.js`.
- **Optional tagging** — `monitor/features.py`: zero-crossing-rate → `bark-like` /
  `ambient` with a single hardcoded 0.10 threshold; attached in
  `monitor/service.py:_attach_tag` from a pruned in-memory feature buffer.
- **Pipeline & ops** — `monitor/service.py:run_pipeline` is a pure generator
  (frame → level → detector → store), with the CLI adding sessions, retention pruning,
  and a heartbeat (`monitor/health.py`, atomic `os.replace` write).
- **Store** — `store/db.py`: SQLite in WAL, `PRAGMA user_version` migrations
  (currently v2), `events` + single-row `calibration` + `sessions` (lineage: device,
  mic, placement, tz, calibration, frame coverage). The schema itself is the privacy
  guarantee — no column can hold audio.
- **Reporting** — `report/aggregate.py` (tz-aware bucketing), `report/charts.py`
  (deterministic hand-rendered SVG + paired data tables), `report/render.py`
  (self-contained HTML, mandatory Methodology/Limitations constants that the
  report-content gate checks), `report/violations.py` (all-events honest quiet-hours
  export), `report/export.py` (CSV).
- **PWA** — `pwa/app.js` (Web Audio `AnalyserNode` → `dbfs` → `Detector` → IndexedDB),
  `pwa/report.js` (parallel aggregation/report/CSV), `pwa/sw.js`, tested with
  `node --test` (`pwa/*.test.mjs`).
- **Enforcement** — `tests/test_no_audio.py` (dataclass/schema introspection + AST and
  string scans + binary-write-open scan), `tests/test_no_egress.py` (import scan +
  socket booby-trap over the full pipeline), snapshot determinism
  (`tests/test_report_snapshot.py`), Hypothesis properties, structural a11y in pytest
  plus pa11y/axe in CI (`.github/workflows/ci.yml`), 2-OS × 5-Python matrix, hardened
  systemd unit (`deploy/olive-monitor.service`: `PrivateNetwork`, `ProtectSystem=strict`,
  `RestrictAddressFamilies=AF_UNIX`).

## What is genuinely strong

- **The guarantee is architectural, not aspirational.** There is literally no API that
  writes a frame; the gate tests would fail any PR that adds one. The no-audio proof doc
  (`docs/audits/no-audio-guarantee.md`) matches the code as read.
- **Determinism as a testing strategy.** Byte-stable SVG charts and `generated_at`
  injection make the whole report snapshot-testable — rare discipline for HTML output.
- **Honesty is load-bearing copy.** `RELATIVE_DBFS_NOTE`, `NO_SOURCE_NOTE`, and
  `HONEST_SCOPE_NOTE` are constants shared between renderer and tests, so the honest
  framing is merge-blocking, not a docs promise.
- **The violations export lists *all* events** (`report/violations.py`), making
  cherry-picking structurally impossible — a genuinely novel anti-abuse design.
- **Ops texture beyond a toy**: sessions/lineage, frame-coverage accounting, WAL +
  migrations, retention pruning, resilient reconnect, atomic heartbeat.

## Structural debt and gaps actually observed

1. **Branch integration debt.** The entire 2026-06-30 research layer — both documents
   and the shipped R1/R2/R3/R5 code (cover page, calibration banner, duration rollup,
   no-audio note, `--reference-instrument`) — sits on `research-panel-and-roadmap`,
   unmerged. `ci-efficiency` (CI caching, macOS-off-PR) is also unmerged. `main` today
   does not have the honesty-surfacing features the README of that branch describes.
2. **Calibration has two sources of truth, and the monitor clobbers one.**
   `monitor/service.py:115` unconditionally calls
   `store.set_calibration(config.calibration_offset, …)` at startup — so running
   `olive-calibrate` (which stores an offset in the DB) and then `olive-monitor` with a
   default config **overwrites the stored calibration back to 0.0**. Meanwhile
   `run_pipeline` levels events with `config.calibration_offset` (offset baked into
   stored dBFS) while `generate_report_from_db` prefers the DB calibration row. Mixed
   epochs are not reconcilable after the fact. See FIX-01.
3. **The PWA has drifted from the Python core.** It lacks calibration entirely, lacks
   sessions/coverage accounting, and (once the research branch lands) will lack the
   cover page/banner/rollup — that branch touched only Python. Two sharper issues
   observed by reading `pwa/app.js`: events are timestamped with
   `audioCtx.currentTime` (seconds since AudioContext creation), yet `pwa/report.js`
   interprets `ev.start` as unix seconds (`new Date(ev.start * 1000)`) — which would
   date every live-captured PWA event to January 1970 (strongly indicated by reading;
   unverified because nothing was run); and the sampling loop runs on
   `requestAnimationFrame`, which browsers throttle or pause in background tabs, so
   monitoring silently stops with no coverage record. See FIX-05/FIX-06.
4. **No browser-side guarantee gates.** `tests/conftest.py:source_files()` scans only
   `monitor/store/report` Python. Nothing forbids a future `MediaRecorder`, `fetch`, or
   `sendBeacon` in `pwa/*.js`; the PWA's no-audio promise is enforced only by review.
   pa11y runs against the Python report, not `pwa/index.html`. See FIX-07.
5. **Report describes the present, not the past.** Sessions record calibration and
   placement but **not** `threshold_dbfs`/`min_duration_s`/`debounce_s`; the Methodology
   section renders the *current* config values against events possibly logged under
   different ones, and `render.py` shows only `latest_session()` conditions even when
   events span many sessions. See FIX-02.
6. **Quiet ≠ unmonitored is not representable.** Heatmap zero-count cells
   (`charts.py:_HEAT_EMPTY`) look identical whether the night was silent or the mic was
   unplugged; outage intervals are not persisted (only queue-drop counts are). Absence
   of events is being presented as evidence of quiet. See FIX-03 (goes beyond E7).
7. **Heartbeat and counters are event-driven, not time-driven.** `service.py` writes
   the heartbeat at start, per event, and in `finally`; a silent night leaves it stale
   for hours (false watchdog alarms), and `frames_seen` reaches the DB only in
   `finally` (lost on SIGKILL/power cut). See FIX-04.
8. **Attribution is start-time-only everywhere** (`aggregate.py`, `violations.py`, and
   the branch's R3 rollup): an event running 21:30→22:40 contributes zero quiet-hours
   loud time. Conservative in that direction, but the same rule *over*-attributes an
   event starting 07:59. See FIX-09.
9. **QuietHours is integer-hours, single-window** (`monitor/config.py`) — cannot
   express 22:30 starts or weekend-different ordinances, which E5 (jurisdiction
   templates) will immediately need. See FIX-08.
10. **Eval realism.** `tests/test_eval.py` and `monitor/capture.py` validate detection
    against 440 Hz sine regions; the ZCR classifier threshold has never met a real bark.
    ROADMAP §4's labeled real session remains an open, honestly-deferred real-data gate.
11. **Standards conformance edges**: no tags/CHANGELOG/SBOM/release pipeline (v0.1.0,
    no releases), no `zizmor` in CI despite the CI-CD standard naming it; coverage
    floor is 85% (`pyproject.toml`), with actual coverage unverified here since tests
    were not run.

## Strategic position in the portfolio

This is the portfolio's cleanest demonstration of **privacy-by-design under a real
adversarial constraint** — the "produces evidence, not vibes" repo. Its enforcement
pattern (design out the dangerous API, then gate it with static+behavioral tests) is
the same pattern `self-osint-monitor` needs, which makes the gate suite a candidate for
extraction into `/STANDARDS` (EXP-08). It is also the repo where the portfolio's
honesty ethos is most concrete: calibration banners, no-verdict rollups, and
all-events exports are *features*. The biggest strategic risk is quiet divergence — a
main branch that doesn't carry the research layer, and a PWA that no longer matches the
Python semantics it claims to share (`pwa/README.md`'s parity table is currently
aspirational in both directions).
