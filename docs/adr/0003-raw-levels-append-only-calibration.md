# 0003. Store raw dBFS; calibration is an append-only history applied at render time (schema v3)

**Status:** Accepted · **Date:** 2026-07-09

## Context

Two coupled data-integrity defects (roadmap B1, FIX-01; both live in every
`olive-monitor` run before this change):

1. **Calibration clobber.** `monitor/service.py` wrote
   `store.set_calibration(config.calibration_offset, …)` on every start, overwriting the
   single DB calibration row with the config value. Running `olive-calibrate` and then
   `olive-monitor` with a default config silently reverted the device to uncalibrated,
   and pre-fix calibration provenance is unrecoverable by construction (the single row
   was overwritten in place).
2. **Baked-in offsets.** Event levels were stored *offset-adjusted*
   (`dbfs(frame, calibration_offset=…)`), so recalibrating changed the meaning of new
   rows relative to old rows with no reconciliation, corrupting the longitudinal record.

This tool's entire value is honest, longitudinal noise evidence; a stored level whose
meaning depends on when it was written breaks that promise.

## Decision

- **Events store raw dBFS.** No calibration is ever baked into a persisted level.
  `threshold_dbfs` is therefore defined against the raw scale too, so recalibrating
  never changes detection sensitivity (users who tuned a threshold under a baked
  nonzero offset must re-tune — disclosed in `monitor/config.py` and the README).
- **Calibration is an append-only history** (`calibration_history`: `effective_from`,
  `offset`, `note`, `reference_instrument`), schema **v3**. `olive-calibrate` is the
  only production writer and records `--reference-instrument` provenance. The v2→v3
  migration preserves any legacy `calibration` id=1 row as epoch 0
  (`effective_from = 0`).
- **Calibration is applied at render time, uniformly.** A single per-event resolver
  (`report/render.py::_per_event_offsets`; attribution by event *start*) feeds the HTML
  report **and** every export (`--csv`, `--violations-csv`, `--violations-html`), so no
  two artifacts generated from the same log can disagree numerically. Each CSV row
  records the offset included in its values (`calibration_offset_db`; raw = value −
  offset), and the violations report derives its calibrated/uncalibrated statement from
  the store's history — never from the deprecated config field. Windows spanning more
  than one epoch render a per-epoch disclosure.
- **Migration timestamps are recorded** in a `schema_migrations` table
  (`version`, `applied_at`), written by `EventStore._migrate` from this version on.
  The v3 timestamp is the **era boundary**: sessions/events written before it may carry
  a baked-in offset; rows after it are raw. Migrations applied by older binaries have no
  row (time of application honestly unknown).
- `config.calibration_offset` / `calibration_note` are **bootstrap-only (deprecated)**:
  they seed a never-calibrated database and are ignored once history exists.

## Consequences

- Re-rendering any historical date range yields identical numbers before and after a
  recalibration; recalibration provenance is durable from this version forward.
- **Legacy data (honest limits):** default-config histories are numerically unaffected
  (the clobber itself forced the stored offset to 0.0, so stored levels already equal
  raw dBFS). If a nonzero `calibration_offset` was ever configured pre-v3, those events
  carry it baked in and epoch 0 re-applies it at render — they render over-adjusted.
  No automated rewrite of historical rows is performed; recovery, where session links
  exist (schema v2+), is `raw = stored − sessions.calibration_offset` for sessions that
  started before the v3 `applied_at` timestamp. v1-era events with no session link are
  not attributable to an offset and are honestly unrecoverable. Pre-fix calibration
  provenance cannot be reconstructed. The multi-epoch report disclosure states this
  caveat.
- The legacy single-row `calibration` table remains (no writers); dropping it is
  deferred to a future migration so old binaries pointed at a new DB fail soft rather
  than corrupt.
- **Schema versioning discipline:** v3 is taken by this change. Any other pending schema
  change (e.g. FIX-02 parameter provenance, PR #12) must rebase onto this and become
  v4+ — two branches must never both define v3.

## Alternatives considered

- **Rewrite historical rows during migration** (subtract the baked offset): rejected —
  it would silently mutate evidence, and v1 rows have no attributable offset at all.
  Disclosure plus a recorded era boundary is the honest posture.
- **Keep baked-in storage but log calibration changes:** rejected — every render would
  still need per-row era knowledge, and stored numbers would keep changing meaning.
- **Version-bump the app to mark the era** (`sessions.app_version`): weaker than a
  DB-recorded timestamp (the version string does not say when the *database* crossed
  the boundary) and conflated with release semantics; `schema_migrations` records it
  directly.
