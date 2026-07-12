"""Turn a stream of (timestamp, level) readings into noise *events*.

A reading is a single level in dBFS at a wall-clock time. The detector is a small
state machine with three knobs:

  * threshold_dbfs  — a reading at or above this counts as "loud".
  * min_duration_s  — loud has to last at least this long to be a real event
                      (filters single-frame transients: a door, a cough).
  * debounce_s      — once an event is open, dips below threshold shorter than this
                      do not end it (a dog pausing between barks stays one event).

Peak and average are computed over the loud readings only, so avg_level is "how
loud while barking", not diluted by the quiet gaps the debounce bridges.

Alongside those, each event carries a few bounded *envelope descriptors* ("event
anatomy") — rise time, seconds spent well above threshold, and the longest unbroken
loud run — so a report can tell one long drone apart from a burst of sharp barks. These
are all O(1) running counters over timestamps and levels: no audio, no buffering, no
per-frame history. They are shape, never sound.

No audio is involved here at all — only numbers and timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """A detected noise event. Carries metadata only — never any audio."""

    start: float  # unix seconds, first loud reading
    end: float  # unix seconds, last loud reading
    duration: float  # end - start, seconds
    peak_level: float  # max dBFS during the event
    avg_level: float  # mean dBFS over loud readings
    coarse_tag: str | None = None  # optional bark-like/ambient hint (see M-could)
    # -- envelope anatomy (bounded shape descriptors; None on legacy rows) -------------
    rise_time_s: float | None = None  # seconds from start to first reading >= threshold+6 dB
    loud6_s: float | None = None  # total seconds spent at/above threshold+6 dB
    longest_run_s: float | None = None  # longest unbroken above-threshold run (no dip)


class Detector:
    """Streaming detector. Feed readings with push(); collect Events as they close."""

    def __init__(
        self,
        threshold_dbfs: float,
        min_duration_s: float,
        debounce_s: float,
    ) -> None:
        if min_duration_s < 0 or debounce_s < 0:
            raise ValueError("min_duration_s and debounce_s must be non-negative")
        self.threshold = threshold_dbfs
        self.loud6_threshold = threshold_dbfs + 6.0  # "well above": threshold + 6 dB
        self.min_duration = min_duration_s
        self.debounce = debounce_s
        self._active = False
        self._start = 0.0
        self._last_above = 0.0
        self._peak = 0.0
        self._sum = 0.0
        self._n = 0
        # -- envelope-anatomy running state (all O(1), reset in _open) -----------------
        self._prev_t = 0.0  # timestamp of the last reading seen while active
        self._prev_above6 = False  # was that reading at/above threshold+6 dB
        self._first6: float | None = None  # first timestamp at/above threshold+6 dB
        self._loud6 = 0.0  # accumulated seconds spent at/above threshold+6 dB
        self._in_run = False  # currently inside an unbroken above-threshold run
        self._run_start = 0.0  # start timestamp of the current run
        self._best_run = 0.0  # longest run seen so far

    def push(self, t: float, level: float) -> Event | None:
        """Feed one reading. Returns an Event if a previously open one just closed."""
        above = level >= self.threshold

        if not self._active:
            if above:
                self._open(t, level)
            return None

        # An event is open. Fold this reading into the envelope-anatomy counters first,
        # so the loud6/run state is correct whether or not the event closes here.
        self._anatomy_step(t, level, above)

        if above:
            self._last_above = t
            self._accumulate(level)
            return None

        # Below threshold while active: close only if we've been quiet long enough.
        if t - self._last_above >= self.debounce:
            return self._close()
        return None

    def flush(self) -> Event | None:
        """Close any open event at end of stream. Returns it if it qualifies."""
        if self._active:
            return self._close()
        return None

    # -- internals -----------------------------------------------------------
    def _open(self, t: float, level: float) -> None:
        self._active = True
        self._start = t
        self._last_above = t
        self._peak = level
        self._sum = level
        self._n = 1
        # The opening reading is above threshold by construction; seed anatomy state.
        above6 = level >= self.loud6_threshold
        self._prev_t = t
        self._prev_above6 = above6
        self._first6 = t if above6 else None
        self._loud6 = 0.0
        self._in_run = True
        self._run_start = t
        self._best_run = 0.0

    def _accumulate(self, level: float) -> None:
        if level > self._peak:
            self._peak = level
        self._sum += level
        self._n += 1

    def _anatomy_step(self, t: float, level: float, above: bool) -> None:
        """Advance the O(1) envelope-anatomy counters by one reading while active."""
        above6 = level >= self.loud6_threshold
        dt = t - self._prev_t
        # Attribute the just-elapsed interval to loud6 time when it *began* well above
        # threshold and the level never fell below threshold across it. This avoids
        # counting the trailing silence gap that a below-threshold reading opens up.
        if self._prev_above6 and above:
            self._loud6 += dt
        self._prev_t = t
        self._prev_above6 = above6
        if above6 and self._first6 is None:
            self._first6 = t

        # A below-threshold reading ends the current run even if debounce keeps the
        # event open; the next above-threshold reading starts a fresh run.
        if above:
            if not self._in_run:
                self._in_run = True
                self._run_start = t
        elif self._in_run:
            self._best_run = max(self._best_run, self._last_above - self._run_start)
            self._in_run = False

    def _close(self) -> Event | None:
        duration = self._last_above - self._start
        # Finalize any run still open at close (its last above-threshold reading is the
        # event's end); then derive the bounded shape descriptors.
        if self._in_run:
            self._best_run = max(self._best_run, self._last_above - self._run_start)
        rise_time = None if self._first6 is None else self._first6 - self._start
        event: Event | None = None
        if duration >= self.min_duration:
            event = Event(
                start=self._start,
                end=self._last_above,
                duration=duration,
                peak_level=self._peak,
                avg_level=self._sum / self._n if self._n else self.threshold,
                rise_time_s=rise_time,
                loud6_s=self._loud6,
                longest_run_s=self._best_run,
            )
        self._active = False
        return event
