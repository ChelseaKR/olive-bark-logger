# Data Card — Olive's Bark Logger

**Last verified: 2026-06-05 · Recheck cadence: per schema change.**

What data this system holds, why, where, and for how long. The guiding principle is
data minimization: store the least that answers "when was it loud, and for how long?".

## What is collected

| Dataset | Fields | Purpose | Sensitive? |
|---------|--------|---------|-----------|
| `events` | start, end, duration, peak_level, avg_level, coarse_tag, session_id | the noise record the report is built from | No — six numbers + an optional coarse tag; not attributable to a person |
| `sessions` | started_at, ended_at, device_label, mic_model, placement_note, tz, calibration_offset/note, frames_seen, frames_dropped, app_version | lineage: *where/how* a run measured, and whether it kept up with the audio (frame coverage) | No — operator-supplied metadata; do not put personal data in `placement_note` |
| `calibration` | offset, note | convert relative dBFS toward approximate SPL | No |

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
migrations (current version 2). See `store/db.py`.
