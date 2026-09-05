# 0027. Anchor PWA timestamps to the epoch and sample on a timer, not a frame callback (FIX-05)

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
Three defects in the PWA capture path, each of which produced output that looked
correct:

1. **Wrong epoch.** Events were stamped with `AudioContext.currentTime` — seconds since
   the audio context was created — while the report and CSV expect unix-epoch seconds.
   Every PWA event was therefore dated to 1970 plus a few minutes, in a file whose
   format gives no hint that the numbers are relative.
2. **A sampling loop that stops when nobody is looking.** `requestAnimationFrame` is
   throttled to roughly 0 Hz in a backgrounded tab, so locking the phone stopped
   measurement. The record showed quiet.
3. **Unflushed tail.** An event in progress when capture stopped was dropped.

(2) is the coverage defect ([ADR-0016](./0016-frame-coverage-accounting.md)) in the
browser: a gap in measurement rendered as a finding about the world.

## Decision
- **An epoch anchor.** `pwa/clock.js` computes `Date.now()/1000 − currentTime` once and
  maps every reading through `toEpochSeconds`, so PWA timestamps mean what the Python
  path's timestamps mean.
- **A steady `setInterval`** replaces the `requestAnimationFrame` sampling loop, cleared
  on stop.
- **`visibilitychange` records `{ kind: 'gap', start, end }`** coverage holes for hidden
  or locked periods. `summarize` and the CSV exports **exclude** them from event counts,
  and the report surfaces them as honest **"monitoring gaps"**.
- **Any in-progress detector event is flushed on stop.**

Covered by `pwa/clock.test.mjs`.

## Consequences
- **Easier:** a PWA run is comparable with a Pi run, and a partial night is legible as a
  partial night rather than a quiet one.
- **Consistent:** the gap record is the browser's version of frame-coverage accounting,
  which is why it is excluded from counts *and* disclosed rather than either alone.
- **Harder / accepted:** a backgrounded tab genuinely cannot measure. This decision
  makes the hole visible; it does not fill it, and the PWA remains the weaker record of
  the two.
