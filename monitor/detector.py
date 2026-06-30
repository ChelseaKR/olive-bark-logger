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
        self.min_duration = min_duration_s
        self.debounce = debounce_s
        self._active = False
        self._start = 0.0
        self._last_above = 0.0
        self._peak = 0.0
        self._sum = 0.0
        self._n = 0

    def push(self, t: float, level: float) -> Event | None:
        """Feed one reading. Returns an Event if a previously open one just closed."""
        above = level >= self.threshold

        if not self._active:
            if above:
                self._open(t, level)
            return None

        # An event is open.
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

    def _accumulate(self, level: float) -> None:
        if level > self._peak:
            self._peak = level
        self._sum += level
        self._n += 1

    def _close(self) -> Event | None:
        duration = self._last_above - self._start
        event: Event | None = None
        if duration >= self.min_duration:
            event = Event(
                start=self._start,
                end=self._last_above,
                duration=duration,
                peak_level=self._peak,
                avg_level=self._sum / self._n if self._n else self.threshold,
            )
        self._active = False
        return event
