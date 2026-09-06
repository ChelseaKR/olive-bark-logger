# 0016. Count frames seen against frames dropped, and disclose the coverage

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
Audio capture applies backpressure silently. If the level pipeline cannot keep up, or
the device stalls, PortAudio drops frames and the process continues. Nothing in the
event log records the difference, so the failure looks exactly like quiet: fewer events,
a clean-looking night, and a report that under-counts the very thing it was installed to
count.

This is the same defect class as [ADR-0008](./0008-mandatory-methodology-and-limitations.md)'s
premise, in its most dangerous direction — a shortfall in the measurement rendered as a
finding about the world.

## Decision
The capture path **counts frames seen and frames dropped**, per session, and the
report's **"Measurement conditions"** section discloses the resulting coverage. A run
that saw 60% of its frames says so; a run with full coverage says that too, so the
absence of a warning is itself informative rather than ambiguous.

This is the integrity complement to the no-audio guarantee: no-audio says what the
record deliberately does not contain, coverage says what it accidentally does not
contain.

## Consequences
- **Easier:** an under-counting run is visible in its own output instead of being
  indistinguishable from a quiet one.
- **Downstream:** coverage became the shape every later disclosure took — recorded
  monitoring gaps, off-air hours, quiet-hours window coverage — and the failure to
  apply it consistently is what several later fixes were about. The general rule this
  established is now held by `tests/test_absence_as_value.py`.
- **Harder / accepted:** the counters have to survive a crash to be worth anything,
  which is what [ADR-0021](./0021-time-driven-heartbeat-and-crash-safe-counters.md)
  addresses.
