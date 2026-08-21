# Derived-Data Privacy Budget

**Status:** Enforced as a provisional engineering ceiling on 2026-07-12; extended
2026-08-04 to cover the opt-in ambient baseline ledger (EXP-01, `minute_levels`).
External privacy-SME review is still required before calling either ceiling validated.

Olive's Bark Logger may persist enough derived metadata to answer “when was it loud,
for how long, and under what measurement conditions?” It must not persist a level
trace, spectral representation, embedding, or any value from which sound could be
reconstructed. This budget makes that boundary reviewable and testable.

## Enforced ceiling

- Persisted datasets are limited to events, capture sessions, calibration epochs,
  monitoring gaps, clock anomalies, the opt-in ambient-minute ledger, and migration
  bookkeeping. A new table is a privacy-budget change and must update the gate in
  `tests/test_privacy_budget.py`.
- Each event may carry at most five signal-derived scalars: `peak_level`, `avg_level`,
  `rise_time_s`, `loud6_s`, and `longest_run_s`. Timestamps, duration, and `session_id`
  are timing/lineage metadata; `coarse_tag` is one optional categorical hint.
- Each ambient-ledger minute (`minute_levels`, opt-in, off by default) may carry at
  most four signal-derived scalars: `min_dbfs`, `median_dbfs`, `max_dbfs`, and
  `l90_dbfs`. `minute_start` and `session_id` are timing/lineage metadata;
  `frame_count` is a coverage counter (how many readings the summary was computed
  over), the same category as `sessions.frames_seen`, not signal content.
- Signal-derived values are bounded per-event or per-minute summaries only. Per-frame
  or sub-minute periodic level rows, sample arrays, histograms, frequency bins,
  spectra, embeddings, and fingerprints are outside the budget.
- No persisted field may contain binary data or use a name associated with raw audio
  or spectral content. Existing no-audio tests enforce the binary/raw-audio half; the
  privacy-budget test enforces table, event-column, minute-column, and signal-field
  ceilings.
- A budget increase requires a deliberate edit to this document and its gate in the
  same reviewed change. Silence from the test suite is not approval.

The ceiling is record-based instead of claiming a single fixed scalars-per-minute rate
across the whole schema. Event frequency depends on the configured threshold, minimum
duration, debounce, and frame cadence, so a universal per-minute number would be
misleading there. The ambient ledger is the one place a true per-minute rate is
meaningful and stated explicitly (four scalars, one row, every 60 seconds while
enabled) precisely because it is a fixed-cadence summary, not an event-triggered one.

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

**Ambient baseline ledger (`minute_levels`, EXP-01) — the incremental risk beyond the
event ledger.** The event ledger only ever reveals *loud* moments; the ambient ledger
adds a continuous record of the room's baseline (min/median/max/L90 dBFS) every minute
while enabled. The added information is coarse and time-diluted, not richer per
instant:

- Sixty seconds of audio is reduced to four extrema/percentile numbers with no
  ordering, no timing within the minute, and no waveform shape. Reconstructing
  speech, or even distinguishing "TV on" from "conversation" from "silence with a
  fan running," requires temporal and spectral resolution this summary structurally
  discards — the same reasoning `docs/audits/no-audio-guarantee.md` applies to
  events, extended to a coarser, periodic sampling instead of a sparse, triggered one.
- The genuine new capability is *continuity*: an adversary with full database access
  who could previously only see loud crossings can now see that the device was
  recording *something* every minute it ran, and roughly how loud the room's baseline
  was. Combined with existing session lineage (placement, timezone), a long enough
  history could support a coarser version of the same occupancy-pattern inference the
  event ledger already permits — not a new capability in kind, but a smoother,
  denser signal in degree. This is why the feature defaults **off**
  (`config.ambient_ledger = False`): enabling it is an explicit operator choice to
  accept that denser signal in exchange for the evidentiary value (event-to-ambient
  contrast, dead-mic-vs-quiet-night disambiguation) described in
  `docs/ideation/03-expansions.md`'s EXP-01 entry.
- No spectral, frequency-domain, or waveform-shaped value is computed or stored at
  any point — the same forbidden-field scan that covers `events` (`derived-data-budget`
  ceiling + `tests/test_no_audio.py`) covers `minute_levels` identically, since both
  scans are schema-generic rather than table-specific.

## Review gate

A qualified audio-privacy or re-identification reviewer must assess whether the five
signal-derived scalars per event, the four signal-derived scalars per ambient-ledger
minute, and the possible event/minute rate together create a practical speech-activity
or occupancy risk beyond the stated posture. Until that review is committed, this
document is an enforced engineering limit, not a claim of expert-validated safety —
consistent with how EXP-06's PDF/UA claim and FIX-13's original ceiling are each
marked human-gated rather than silently treated as done.
