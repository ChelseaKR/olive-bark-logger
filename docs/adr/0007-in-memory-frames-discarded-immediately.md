# 0007. Frames are processed in memory and discarded immediately

**Status:** Accepted · **Date:** 2026-05-31 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
[ADR-0005](./0005-level-only-no-audio-persisted.md) says no audio is persisted. That is
a claim about outcomes, and there is a tempting implementation that satisfies it only
by convention: buffer raw frames to disk (a ring buffer, a crash-recovery spool, a
"just while we compute" scratch file) and delete them afterwards. Audio on disk that
is *meant* to be deleted is still audio on disk — recoverable, backed up, and captured
by any snapshot taken in the window.

## Decision
Each captured frame is converted to a level (RMS → dBFS) **in memory** and dropped
before the next frame is read. Nothing between the capture callback and the level is
retained, spooled, or written. The detector and every downstream consumer see levels
and timestamps, never samples.

**Rejected: buffering raw audio to disk**, in any form or for any duration.

## Consequences
- **Easier:** the no-audio guarantee is checkable — there is no write path to inspect
  for correctness, because there is no write path.
- **Easier:** memory is bounded by construction on a small Pi, with no buffer to size.
- **Harder / accepted:** nothing can be recomputed after the fact. If a detection
  parameter was wrong, the past cannot be re-analysed — only re-measured. The
  parameter-provenance record ([ADR-0019](./0019-detection-parameter-provenance.md))
  exists so that at least the past is *interpretable* under the settings that produced
  it.
- **Harder / accepted:** per-event descriptors have to be computed as the event happens
  ([ADR-0025](./0025-bounded-per-event-envelope-stats.md)), as O(1) running counters,
  rather than derived later from a buffer.
