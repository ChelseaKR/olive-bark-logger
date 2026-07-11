# Large-Scale Fixes (FIX-01 … FIX-13) — 2026-07-01

Deep structural fixes observed from the code, none of which appear in `ROADMAP.md` or
`RESEARCH-ROADMAP.md` (R1–R9/E1–E7 are referenced where an item builds beyond them).
Effort tiers: S ≈ a day · M ≈ 2–4 days · L ≈ 1–2 weeks · XL ≈ multi-week.

---

## FIX-01 · Calibration single source of truth + raw-level storage
**Pitch:** Stop the monitor from clobbering stored calibration, and stop baking the
offset into persisted levels.
**Why it matters:** Today `monitor/service.py:115` overwrites the DB calibration row
with the config value on every start — `olive-calibrate` followed by `olive-monitor`
with a default config silently reverts the device to "uncalibrated." Worse,
`run_pipeline` applies `config.calibration_offset` inside `level.dbfs()`, so events
persist *offset-adjusted* dBFS; recalibrating changes the meaning of new rows relative
to old ones with no way to reconcile. For a tool whose entire value is a trustworthy
longitudinal record, this is the most corrosive defect in the repo.
**Shape of work:** (a) store **raw** dBFS in `events` and apply offsets at render time;
(b) turn `calibration` into an append-only history table (migration v3 in
`store/db.py:_MIGRATIONS`) keyed by effective-from timestamp, carrying the
`--reference-instrument` provenance the research branch added to
`monitor/calibrate.py`; (c) `olive-monitor` reads calibration from the store and never
writes it; config's `calibration_offset` becomes a bootstrap-only value with a loud
deprecation note; (d) report renders per-epoch offsets and discloses recalibration
points.
**Effort:** M. **Risks/deps:** schema migration on live DBs; threshold comparison
(`Detector`) must be defined against raw or adjusted levels — pick raw and document it;
interacts with FIX-02 (session provenance) and the R2 banner (branch). Snapshot tests
churn.
**Excellent looks like:** a property test proving `calibrate → monitor → report`
round-trips the offset; re-rendering any historical date range yields identical numbers
before and after a recalibration; zero code paths that write calibration outside
`olive-calibrate`.

## FIX-02 · Detection-parameter provenance per session
**Pitch:** Record threshold/min-duration/debounce (and effective config) in `sessions`,
and make the report describe the parameters *in force when each event was logged*.
**Why it matters:** `store/db.py`'s `sessions` table records placement/calibration/tz
but not the three detection knobs; `report/render.py` prints
`config.threshold_dbfs` in Methodology. Change the threshold in week 2 and the report
misdescribes week 1 — exactly the "tuned numbers presented as objective truth" risk the
bias audit (`docs/RESPONSIBLE-TECH-AUDITS.md` §B) commits against. Also
`render.py:_conditions_html` shows only `latest_session()`, hiding placement changes.
**Shape of work:** migration adding `threshold_dbfs`, `min_duration_s`, `debounce_s`,
`sample_rate`, `frame_size` to `sessions`; `summarize()` gains per-session grouping;
Methodology becomes a small table of parameter epochs when >1 session differs;
a "settings changed during this record" disclosure line (honesty-as-a-feature: disclose
it, don't smooth it over).
**Effort:** M. **Risks/deps:** report layout churn; pairs naturally with FIX-01's
migration (ship as one v3). **Excellent looks like:** a merge-blocking test that renders
a two-session DB with different thresholds and asserts both parameter sets appear;
no report can ever describe an event with parameters it wasn't detected under.

## FIX-03 · Monitoring-gap ledger: make "no data" first-class
**Pitch:** Persist the intervals when the device was *not* listening and render them
distinctly from silence.
**Why it matters:** Absence of events currently reads as quiet. `resilient_source`
(`monitor/capture.py`) retries through outages without recording their duration;
`charts.py` heatmap paints unmonitored hours with the same `_HEAT_EMPTY` as genuinely
quiet hours. An adjudicator (or the accused neighbor's counsel) should be able to see
"device offline 02:10–04:32," and honest reporting demands it. E7 surfaces the existing
coverage *percentage*; this goes beyond it by persisting *when* coverage was lost.
**Shape of work:** a `gaps` table (session_id, start, end, reason ∈ {device-error,
shutdown, clock-jump}); `resilient_source` reports outage spans via a callback;
session start/end deltas synthesized into gaps; heatmap gains a third visual+textual
state ("not monitored", hatched + labeled in the data table so it is not color-only);
the violations export grows a `monitored` column.
**Effort:** M. **Risks/deps:** heatmap/table snapshot churn; depends on FIX-04 for
crash-time gap closure; PWA parity via FIX-06. **Excellent looks like:** a test that
kills the synthetic source mid-session and asserts the report shows the gap; the
methodology states total monitored vs wall-clock time for the reporting window.

## FIX-04 · Time-driven heartbeat and crash-safe counters
**Pitch:** Heartbeat on a clock, not on events; flush session counters periodically.
**Why it matters:** `monitor/service.py` writes the heartbeat only at start, per event,
and in `finally` — a quiet night makes a healthy monitor look wedged (defeating the
watchdog the unit file comments recommend), and `frames_seen`/`frames_dropped` reach
SQLite only in `finally`, so a power cut (the normal Pi failure mode) loses the
coverage record that R6/E7 want to surface.
**Shape of work:** a monotonic-time check inside the pipeline loop (no threads needed:
piggyback on frame cadence, ~10 Hz) writing heartbeat + `update_session` every N
seconds; add `WatchdogSec=` + `Type=notify`/`sd_notify` (stdlib socket to
`$NOTIFY_SOCKET` is AF_UNIX — already permitted by `RestrictAddressFamilies=AF_UNIX` in
`deploy/olive-monitor.service`, and must be exempted-by-design in the egress gate with
a comment, or implemented via the watchdog-file pattern instead).
**Effort:** S–M. **Risks/deps:** the no-egress AST gate (`tests/test_no_egress.py`)
bans `socket` imports — either keep the file-based watchdog (cleaner vs the gate) or
add a narrowly-scoped, tested exception; touches FIX-03. **Excellent looks like:** a
test driving a 2-hour synthetic silent session (virtual clock) asserting heartbeat
freshness throughout and counters durable at every checkpoint.

## FIX-05 · PWA correctness: real timestamps, background-proof capture
**Pitch:** Fix the PWA's clock domain and its silent background-tab blindness.
**Why it matters:** `pwa/app.js` stamps readings with `audioCtx.currentTime` (seconds
since context creation) but `pwa/report.js` treats `ev.start` as unix epoch
(`new Date(ev.start * 1000)`) — as read, every live-captured event would bucket to
1970, making the PWA's report and quiet-hours CSV wrong end-to-end (unverified at
runtime; flagged with that caveat). Separately, the `requestAnimationFrame` loop is
throttled/paused in background tabs, so the "zero-hardware alternative" stops
monitoring the moment the phone locks — with no gap recorded.
**Shape of work:** derive epoch time as
`performance.timeOrigin + performance.now()`-anchored mapping from `audioCtx.currentTime`
at start; replace rAF with an `AudioWorklet` (levels computed on the audio thread,
posted as numbers — strengthens the no-audio story, since raw samples never reach the
main thread) or a `setInterval` fallback; record visibility/suspend intervals as gaps
(pairs with FIX-03); surface "backgrounded tabs cannot monitor reliably" in the UI.
**Effort:** M. **Risks/deps:** AudioWorklet needs serving constraints; test with
mocked clocks in `pwa/detector.test.mjs`-style node tests plus one manual browser pass.
**Excellent looks like:** a node test feeding context-relative times through the fixed
mapping and asserting correct local-date bucketing; documented behavior when the tab is
hidden, with gaps visible in the downloaded report.

## FIX-06 · Cross-implementation conformance harness (Python ↔ PWA)
**Pitch:** One set of golden test vectors that both implementations must pass, so the
parity table in `pwa/README.md` becomes enforced rather than asserted.
**Why it matters:** Drift is already real: the PWA has no calibration concept, no
sessions/coverage, different CSV timezone behavior (`report/export.py` writes ISO in
the report tz; `pwa/report.js:eventsToCsv` hardcodes `toISOString()` UTC), and the
research branch's honesty features are Python-only. Every future feature doubles the
divergence risk.
**Shape of work:** a `spec/` directory of JSON vectors — detector traces
(readings → expected events), summarize inputs → expected aggregates, quiet-hours edge
cases (midnight wrap, DST fall-back) — consumed by a pytest parametrization and a
`node --test` runner; a `SEMANTICS.md` documenting intentional differences (e.g., PWA
has no coarse tagging); CI fails if either side skips a vector.
**Effort:** M. **Risks/deps:** none hard; unblocks R7/E4 and keeps FIX-05 honest.
**Excellent looks like:** adding a new vector is the *only* way to change detection
semantics; a deliberate mutation in either implementation fails both CI legs.

## FIX-07 · Browser-side no-audio / no-egress / a11y gates
**Pitch:** Give `pwa/` the same merge-blocking guarantees the Python core has.
**Why it matters:** `tests/test_no_audio.py` and `test_no_egress.py` scan only
`monitor/store/report` (see `tests/conftest.py:source_files`). Nothing today fails a PR
that adds `MediaRecorder`, `fetch()` to a third party, `WebSocket`, or `sendBeacon` to
`pwa/app.js`. And CI's pa11y runs against the rendered Python report only — the
interactive `pwa/index.html` (the surface a phone user actually touches) has no axe
gate.
**Shape of work:** a static-scan test (Python or node) over `pwa/*.js` + `sw.js`
forbidding `MediaRecorder`, `mediaDevices` misuse beyond `getUserMedia({audio})`,
`fetch(`, `XMLHttpRequest`, `WebSocket`, `sendBeacon`, `EventSource`; a strict
`Content-Security-Policy` meta (`default-src 'none'; script-src 'self'; …`) in
`index.html` as defense-in-depth; add `pa11y` against `pwa/index.html` in
`.github/workflows/ci.yml`; extend `docs/audits/no-audio-guarantee.md` with the
browser column.
**Effort:** S. **Risks/deps:** `sw.js` legitimately uses cache APIs — allowlist
precisely. **Excellent looks like:** the guarantee doc can say "enforced in both
implementations" and point at two merge-blocking tests; axe-clean on the PWA UI.

## FIX-08 · Quiet-hours schedule model (minutes, weekdays, multiple windows)
**Pitch:** Replace integer `start_hour`/`end_hour` with a real schedule type.
**Why it matters:** `monitor/config.py:QuietHours` cannot express 22:30, weekend-vs-
weekday windows, or split windows — shapes real ordinances and CC&Rs actually take
(the research pass's own E5 jurisdiction templates are unimplementable on the current
model). This is the data-model prerequisite the research roadmap silently assumes.
**Shape of work:** `QuietSchedule` = list of (days-of-week, start-minute, end-minute)
windows with validation and midnight-wrap semantics; JSON config accepts both old and
new forms (old form auto-upgrades, loudly); `contains()` and the R3 rollup consume the
schedule; PWA inputs gain minute granularity via FIX-06 vectors.
**Effort:** M. **Risks/deps:** touches `aggregate.py`, `violations.py`, branch R3 code,
PWA; DST edge cases need vectors (a 22:30 start on fall-back night). **Excellent looks
like:** property tests over arbitrary schedules (Hypothesis) proving every instant is
classified consistently by Python and JS; E5 becomes a pure data problem.

## FIX-09 · Interval-overlap attribution (pro-rated, disclosed)
**Pitch:** Attribute loud *seconds* to the buckets they actually occurred in, not to
the event's start bucket — and disclose the rule either way.
**Why it matters:** `aggregate.py` and `violations.py` (and the branch's R3 rollup)
attribute whole events by start time. An event 21:30→22:40 adds 0 s to quiet hours; one
starting 07:59 adds its full duration. Both directions are attackable by a skeptic and
both misstate the physical record. The current rule is at least stated
(`HONEST_SCOPE_NOTE`), but stating a crude rule is weaker than computing the honest one.
**Shape of work:** split each event's [start,end] across bucket boundaries (hour, day,
quiet-window edges) for *duration* metrics while keeping event *counts* start-attributed
(counts can't be fractional — say so); show both figures during the transition; update
CSV with `seconds_within_quiet_hours` per row.
**Effort:** M. **Risks/deps:** snapshot churn; must land after FIX-08 so the boundary
set is the schedule's; the no-verdict framing from R3 carries over verbatim.
**Excellent looks like:** invariant tests: summed pro-rated seconds equal total event
seconds exactly; a boundary-straddling event contributes to both sides in proportion.

## FIX-10 · Clock-integrity guard
**Pitch:** Detect and record wall-clock jumps so timestamps carry a trust signal.
**Why it matters:** Everything is `time.time()` (`monitor/service.py`,
`capture_live.py`), and the hardened unit runs with `PrivateNetwork=true` on hardware
(Raspberry Pi) that has no RTC — after a power cut the clock can be hours wrong until
NTP (outside the sandbox) fixes it, and a skeptic can fairly ask whether timestamps
were ever manipulated. Evidence whose clock lineage is undocumented is soft evidence.
**Shape of work:** track `time.monotonic()` alongside wall time in the pipeline; a
divergence beyond tolerance records a `clock-jump` gap row (FIX-03's table) with
before/after wall times; sessions record boot-time and tz-database version; the report's
Measurement conditions disclose any clock anomalies in the window.
**Effort:** S–M. **Risks/deps:** FIX-03 table; false positives from suspend/resume on
laptops — classify rather than alarm. **Excellent looks like:** a synthetic test
injecting a 2-hour wall-clock jump and asserting a disclosed anomaly; zero anomalies on
a clean run.

## FIX-11 · Harden the guarantee gates themselves
**Pitch:** Close the gaps a determined future change could slip through the no-audio /
no-egress scanners.
**Why it matters:** `tests/test_no_egress.py` bans network imports but not
`subprocess`/`os.system`/`ctypes` (a `subprocess.run(["curl", …])` passes today);
`test_no_audio.py`'s binary-write scan checks only literal `open(…, "b…")` calls, not
`Path.write_bytes` or `os.open`. The gates are excellent; they should be adversarially
complete, because the audits cite them as proof.
**Shape of work:** extend forbidden-API lists (`subprocess`, `os.system`, `os.popen`,
`ctypes`, `Path.write_bytes`, `os.open` with `O_WRONLY`); extend the runtime booby-trap
to patch `subprocess.Popen`; add the same-spirit scans to the PWA gate (FIX-07); add a
"gate self-test" that plants a canary violation in a fixture and asserts each scanner
catches it.
**Effort:** S. **Risks/deps:** none; `scripts/` uses no subprocess today (verified by
reading). **Excellent looks like:** each scanner has a canary test proving it still
bites; `docs/audits/no-audio-guarantee.md` enumerates the closed bypasses.

## FIX-12 · Branch integration + release discipline
**Pitch:** Land the unmerged work, then give the repo a real release story.
**Why it matters:** The repo's highest-leverage shipped work (R1/R2/R3/R5 +
`RESEARCH-ROADMAP.md`/`USER-RESEARCH.md`) is invisible on `main`
(`research-panel-and-roadmap`, `0f98ce0`), as is the CI-efficiency work
(`ci-efficiency`). Separately there are no tags, no CHANGELOG, no SBOM, and no `zizmor`
workflow-lint despite `/STANDARDS` (CI-CD, Release, Supply-chain) requiring them —
a credibility gap for a repo whose pitch is "evidence you can trust."
**Shape of work:** merge (or rebase-and-merge) the two branches; then: CHANGELOG.md
(Keep-a-Changelog), `v0.2.0` signed tag, a release workflow producing an SBOM
(CycloneDX via `pip-audit`/`cyclonedx-py`) and attaching `report`-side wheels; add
`zizmor` to CI; document the release gate in ROADMAP §7's table.
**Effort:** S–M (merges are review work, not code). **Risks/deps:** snapshot conflicts
between branches (`tests/snapshots/report.html` differs); owner review required — this
is deliberately *not* something to automate past a human.
**Excellent looks like:** `main` == the best known state; a tagged, changelogged,
SBOM'd release; `git branch -a` shows no stranded feature branches.

## FIX-13 · A written, tested "derived-data privacy budget"
**Pitch:** Formalize the boundary for *what derived numbers may ever be persisted*, so
future features are judged against a rule instead of vibes.
**Why it matters:** Today the implicit rule is "six numbers per event plus a tag."
Several attractive expansions (EXP-01 ambient ledger, EXP-02 event anatomy, richer
tags) persist *more* derived data, and each step edges toward reconstructability —
research literature shows even low-rate spectral features can leak speech activity
patterns. The repo's privacy posture deserves the same rigor as its no-audio gate: a
stated information ceiling (e.g., "≤ N scalar values per minute, none spectral below
1-second aggregation"), a rationale, and a test that fails when a schema change exceeds
it. This pattern is directly reusable by `self-osint-monitor`, which shares the
threat-model style.
**Shape of work:** `docs/audits/derived-data-budget.md` (threat analysis: what could an
adversary with full DB access infer? speech activity: no; occupancy patterns: partially
— already true of events; say so honestly); a schema-introspection test extending
`test_db_schema_has_no_audio_column` that counts persisted scalars/second against the
declared budget; review-gate any budget increase.
**Effort:** M (mostly analysis + writing, small test). **Risks/deps:** blocks/gates
EXP-01/EXP-02 by design — that is the point. Privacy-SME review is the honest gate for
the budget numbers themselves. **Excellent looks like:** every future "store more
numbers" PR must edit the budget doc and its test in the same diff, making the privacy
trade-off visible in review forever.
