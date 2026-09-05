# 0019. Each session records the detection parameters its events were logged under (FIX-02)

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
An event means "the level was above the threshold for longer than the minimum duration,
with debounce bridging gaps". Change any of those numbers and the same night produces a
different set of events. The report's Methodology section sourced those numbers from
the *current config*, so re-tuning the detector silently rewrote the description of
events that were logged under the old settings — and a log spanning a tuning change was
described entirely under whichever settings happened to be in force at render time.

Frames are discarded ([ADR-0007](./0007-in-memory-frames-discarded-immediately.md)), so
the past cannot be re-analysed under new parameters. That makes recording the old ones
the only way the old events stay interpretable.

## Decision
Each capture session **records the threshold, minimum duration, debounce, sample rate
and frame size in force when its events were logged** (schema v3). The report sources
its Methodology numbers **from the session**, and when settings changed across sessions
it renders a **"parameter epochs" table** plus a disclosure that each event is described
under the parameters active when it was logged.

Legacy pre-v3 sessions read those columns back as `None` and fall back to config — an
honest "not recorded", not an assumed value.

## Consequences
- **Easier:** re-tuning the detector is safe. It changes future events without
  retroactively re-describing past ones.
- **Consistent:** this is the same shape as calibration
  ([ADR-0003](./0003-raw-levels-append-only-calibration.md)) — record what was in
  force, apply it per row, disclose when a window spans more than one epoch — arrived
  at independently for detection parameters.
- **Harder / accepted:** a report spanning several tunings is more complicated to read
  than one that pretends a single set of numbers applied throughout. That complexity is
  the truth of the record.
