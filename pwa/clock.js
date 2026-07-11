// Pure clock mapping: AudioContext.currentTime is seconds elapsed since the context
// was created, not a wall-clock time. report.js and the CSV exports expect unix-epoch
// seconds (new Date(ev.start * 1000)). We capture one anchor at start and add it to
// every context time so stored events carry real timestamps. Numbers only; no audio.

// Anchor captured once at start: the epoch-seconds value that context-time 0 maps to.
// anchor = Date.now()/1000 - audioCtx.currentTime, so anchor + currentTime === now.
export function computeAnchor(nowMs, ctxTime) {
  return nowMs / 1000 - ctxTime;
}

// Map an AudioContext.currentTime reading to unix-epoch seconds via the anchor.
export function toEpochSeconds(ctxTime, anchor) {
  return anchor + ctxTime;
}
