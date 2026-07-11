# Cross-implementation semantics (Python ↔ PWA)

The Pi monitor (`monitor/`, Python) and the browser PWA (`pwa/`, JavaScript) are
**two ports of the same detection logic**. To stop them drifting apart silently,
`spec/detector/*.json` holds golden test vectors that *both* sides replay:

- `tests/test_conformance.py` runs each vector through `monitor.detector.Detector`.
- `pwa/conformance.test.mjs` runs the same vectors through `pwa/detector.js`.

Both assert the produced events match `expected_events` within `1e-9`.

## The rule

**Changing detection semantics requires changing a vector — on purpose.**

The `expected_events` in each vector were derived by running the real Python
detector (`monitor/detector.py`) and then confirmed to match the JS port. So:

- If you change `monitor/detector.py` or `pwa/detector.js` and a vector now
  fails, that failure *is the drift being caught*. Do not "fix" it by editing
  the vector to match the new output unless the semantic change is intentional.
- An intentional semantic change is landed by updating the affected vector(s)
  (or adding new ones) in the same commit, so both language suites move together.
- New behaviour (a new knob, a new boundary rule) should arrive with a new
  vector that pins it.

## What the detector vectors pin

Each vector fixes the shared state-machine contract:

- `threshold_dbfs` — a reading `>=` threshold is "loud" (the `>=` boundary is
  pinned by `level_exactly_at_threshold_is_loud` and
  `just_below_threshold_no_event`).
- `min_duration_s` — loud must last at least this long, else the event is
  dropped (`single_transient_filtered_by_min_duration`); `min_duration_s == 0`
  keeps a single-frame, zero-duration event (`zero_min_duration_keeps_single_frame`).
- `debounce_s` — a sub-debounce dip keeps one event open
  (`debounce_bridges_dip`); a longer gap splits into two
  (`dip_longer_than_debounce_two_events`).
- `peak_level` / `avg_level` are computed over the **loud readings only**, even
  across a bridged dip (`peak_avg_over_loud_readings_only`,
  `avg_excludes_bridged_dip_reading`).
- An event still open at end of stream is closed by `flush()`
  (`closed_by_flush_at_stream_end`).

## Intentional Python ↔ PWA differences (out of scope for the vectors)

These are deliberate divergences; the conformance harness does **not** try to
force parity on them:

- **PWA has no `coarse_tag` / calibration / sessions.** The JS `Event` object
  carries a `coarse_tag: null` field for shape-compatibility only; the browser
  variant does not compute coarse bark-like/ambient tags, and has no
  calibration-offset or `sessions` lineage table (those are Pi-only, see
  ROADMAP §6 and the P0–P2 ADRs). The vectors therefore assert only the fields
  both implementations own: `start`, `end`, `duration`, `peak_level`,
  `avg_level`.
- **CSV timezone divergence.** The Python and PWA CSV/quiet-hours exports can
  format timestamps against different time zones (fixed-offset vs IANA zone
  handling); this is noted in the FIX-06 roadmap entry and is *not* a detector
  concern, so it is out of scope for `spec/detector/`.

## Extension point: quiet-hours / summarize parity

Both `report/aggregate.py` (Python) and `pwa/report.js` (`summarize`, JS) have
comparable pure quiet-hours/summary functions. A parallel `spec/quiet_hours/*.json`
set (e.g. midnight-wrap windows) could be replayed against both the same way the
detector vectors are. That is intentionally **not** implemented here to keep this
change focused on the detector core; when added, follow the same pattern:
derive expected output from one side, confirm the other agrees, and pin it as a
vector so the timezone/window semantics can no longer drift unnoticed.
