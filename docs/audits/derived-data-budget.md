# Derived-Data Privacy Budget

**Status:** Enforced as a provisional engineering ceiling on 2026-07-12. External
privacy-SME review is still required before calling the ceiling validated.

Olive's Bark Logger may persist enough derived metadata to answer “when was it loud,
for how long, and under what measurement conditions?” It must not persist a level
trace, spectral representation, embedding, or any value from which sound could be
reconstructed. This budget makes that boundary reviewable and testable.

## Enforced ceiling

- Persisted datasets are limited to events, capture sessions, calibration epochs,
  monitoring gaps, clock anomalies, and migration bookkeeping. A new table is a
  privacy-budget change and must update the gate in `tests/test_privacy_budget.py`.
- Each event may carry at most five signal-derived scalars: `peak_level`, `avg_level`,
  `rise_time_s`, `loud6_s`, and `longest_run_s`. Timestamps, duration, and `session_id`
  are timing/lineage metadata; `coarse_tag` is one optional categorical hint.
- Signal-derived values are event summaries only. Per-frame or periodic level rows,
  sample arrays, histograms, frequency bins, spectra, embeddings, and fingerprints
  are outside the budget.
- No persisted field may contain binary data or use a name associated with raw audio
  or spectral content. Existing no-audio tests enforce the binary/raw-audio half; the
  privacy-budget test enforces table, event-column, and signal-field ceilings.
- A budget increase requires a deliberate edit to this document and its gate in the
  same reviewed change. Silence from the test suite is not approval.

The ceiling is record-based instead of claiming a fixed scalars-per-minute rate.
Event frequency depends on the configured threshold, minimum duration, debounce, and
frame cadence, so a universal per-minute number would be misleading. Persisting only
bounded event summaries is the invariant the implementation can actually enforce.

## Threat analysis

Assume an adversary obtains the complete SQLite database and configuration.

- They cannot recover speech, identify words, recreate a waveform, or run a new audio
  classifier: no samples, spectra, embeddings, or frequency-domain values exist.
- They can infer that above-threshold activity occurred at particular times, how loud
  it was relative to calibration, and whether its envelope was continuous or bursty.
- Repeated timing can reveal household routines or probable occupancy. That risk
  already exists in the core event ledger and is not erased by calling the data
  “metadata.” Operators should protect the database and share only the report window
  needed for the dispute.
- `coarse_tag` can bias a reader toward source attribution. It remains optional and
  hedged; the report must continue to say that the tool cannot prove a sound's source.

## Review gate

A qualified audio-privacy or re-identification reviewer must assess whether the five
signal-derived scalars per event and the possible event rate create a practical speech-
activity or occupancy risk beyond the stated posture. Until that review is committed,
this document is an enforced engineering limit, not a claim of expert-validated safety.
