# 0025. Bounded per-event envelope statistics, computed as O(1) counters (EXP-02)

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
`Event(start, end, duration, peak_level, avg_level)` cannot distinguish one long drone
from hundreds of sharp barks in the same window. Those are very different facts about a
neighbourhood, and the difference is the shape of the level envelope inside the event —
which the stored fields discard.

The obvious way to recover shape is to keep the level series, or the frames. Frames are
discarded by construction ([ADR-0007](./0007-in-memory-frames-discarded-immediately.md)),
and an unbounded per-event level series is an unbounded buffer on an appliance that
must run for weeks — the same problem in a thinner disguise.

## Decision
Each event stores **three seconds-valued shape descriptors**, computed as **O(1)
running counters** over levels and timestamps as the event happens, with no buffering:

1. rise time to threshold + 6 dB;
2. total time spent above threshold + 6 dB;
3. the longest unbroken loud run.

They are carried **end to end** — detector → SQLite (schema v7) → CSV and violations
exports — so no artifact describes an event with a different shape than another does.

## Consequences
- **Easier:** a report can tell a drone from a burst pattern, from three numbers per
  event and no new storage class.
- **Bounded by construction:** constant work and constant memory per event, whatever
  its length. An event lasting an hour costs what one lasting a second costs.
- **Migration:** the new columns are nullable and old rows migrate to `None` — an
  honest "not recorded" rather than a computed-looking zero.
- **Deliberate:** the **no-audio gate lists the new fields explicitly**. Adding a
  persisted per-event field is exactly the change that gate exists to make someone
  argue for, and it was argued for rather than waved through.
