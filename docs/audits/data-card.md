# Data Card — Olive's Bark Logger

**Last verified: 2026-06-05 · Recheck cadence: per schema change.**

What data this system holds, why, where, and for how long. The guiding principle is
data minimization: store the least that answers "when was it loud, and for how long?".

## What is collected

| Dataset | Fields | Purpose | Sensitive? |
|---------|--------|---------|-----------|
| `events` | start, end, duration, peak_level, avg_level, coarse_tag, rise_time_s, loud6_s, longest_run_s, session_id | the noise record the report is built from | No — a handful of numbers + an optional coarse tag; not attributable to a person |
| `sessions` | started_at, ended_at, device_label, mic_model, placement_note, tz, calibration_offset/note, frames_seen, frames_dropped, app_version | lineage: *where/how* a run measured, and whether it kept up with the audio (frame coverage) | No — operator-supplied metadata; do not put personal data in `placement_note` |
| `calibration` | offset, note | convert relative dBFS toward approximate SPL | No |

**Envelope anatomy (per-event shape descriptors).** Three bounded seconds-valued
fields let a report distinguish one long drone from hundreds of sharp barks. They are
computed as O(1) running counters over levels and timestamps — no audio, no buffering —
and are `NULL` on rows written before schema v7.
They fit the provisional ceiling in
[`derived-data-budget.md`](./derived-data-budget.md); that ceiling's external
privacy-SME review remains open.

- `rise_time_s` — seconds from the event start to the first reading at/above threshold
  +6 dB (`NULL` if it never got that loud). Justification: separates a slow swell from
  an instant slam without revealing anything about the sound's source.
- `loud6_s` — total seconds the event spent at/above threshold +6 dB. Justification:
  quantifies how much of an event was *emphatically* loud versus merely over the line.
- `longest_run_s` — the longest unbroken above-threshold stretch (a sub-threshold dip
  ends the run even when debounce keeps the event open). Justification: tells a
  continuous drone (one long run) apart from a bark burst (many momentary runs).

**Explicitly never collected:** audio, recordings, speech, voice prints, identities,
locations beyond an operator-typed placement note, or any network/telemetry data.

## Provenance & lineage

Every event links to the `session` that produced it (`session_id`), so each number is
traceable to a device, placement, calibration, time zone, and the frame coverage of that
run. The report's "Measurement conditions" section surfaces this for the reader.

## Storage, location, retention

- **Where:** a single local SQLite file (default `olive.db`) on the device. No cloud.
- **Encryption:** rely on the host's full-disk encryption; the file is not separately
  encrypted (it contains no sensitive content). Set file permissions to the owner only.
- **Retention:** unlimited by default; set `retention_days` to auto-prune older events on
  monitor start (tested in `tests/test_store_durability.py` and `tests/test_cli.py`).
- **Deletion / subject access:** there is no personal data and no third party in the data,
  so there is no subject-access obligation; to erase everything, delete the SQLite file.

## Schema versioning

The schema is versioned via SQLite `PRAGMA user_version` with ordered, in-place
migrations (current version 7). See `store/db.py`.
