# 0017. Detect and record clock jumps during capture (FIX-10)

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
A Raspberry Pi has no real-time clock. It boots with a wrong time and NTP lurches it to
the correct one some seconds or minutes later — and it can lurch again at any point in
a long run. Every event timestamp is taken from the wall clock, so a jump smears the
record: events land in the wrong hour, quiet-hours verdicts move, and durations
computed across the jump are fiction. None of it is visible in the output, because a
timestamp carries no indication that it was taken from a clock that later moved.

## Decision
A **`ClockGuard`** (`monitor/clock.py`) tracks wall time (`time.time`) against
monotonic time (`time.monotonic`) during capture. Divergence beyond a configurable
tolerance — `clock_jump_tolerance_s`, default 2 s — is **persisted** to a
`clock_anomalies` table (schema v3) and **disclosed** in the report's "Measurement
conditions" as a forward or backward jump with the before and after wall times and the
delta. With no anomalies, the report states that, rather than staying silent.

The table is deliberately minimal, and shaped to stay compatible with FIX-03's later
gap table rather than needing to be migrated around it.

## Consequences
- **Easier:** a smeared record is legible as a smeared record.
- **Consistent:** this is the coverage decision
  ([ADR-0016](./0016-frame-coverage-accounting.md)) applied to time instead of frames —
  the integrity complement to it.
- **Harder / accepted:** the guard records the jump; it does not repair the timestamps
  it affected. Reconstructing true times from a monotonic anchor after the fact is
  possible in principle and was not attempted — disclosure was judged the honest floor,
  and correction without disclosure would be worse than either.
