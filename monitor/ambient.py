"""Streaming per-minute ambient level aggregates (EXP-01 ambient baseline ledger).

Today the event log records only threshold *crossings*: there is no record of what
the room's baseline sounded like, so a quiet night and a dead microphone look
identical, and a skeptic can fairly ask whether the threshold was tuned to manufacture
events. This module answers that with a bounded, opt-in summary: every wall-clock
minute is reduced to four numbers (min/median/max/L90 dBFS) plus a frame count,
computed from the same per-frame ``dbfs()`` values the detector already sees.

This is the same shape of guarantee as ``monitor/detector.py``'s envelope anatomy: an
O(1)-per-reading accumulator over *numbers*, never audio. It reads no sample data (the
frame is gone by the time a level reaches here) and it never buffers more than one
wall-clock minute's worth of scalars at a time. See
``docs/audits/derived-data-budget.md`` for the privacy-budget analysis this feature
must (and does) stay inside, and ``monitor/config.py``'s ``ambient_ledger`` flag —
this is off by default; nothing is persisted unless an operator opts in.

L90 is the standard environmental-acoustics "background level" descriptor: the level
*exceeded* 90% of the time. In percentile terms that is the 10th percentile (P10) of
the minute's level distribution -- ascending-sorted, only 10% of readings fall below
it, so 90% are at or above it. (L10, the complementary "intrusive peaks" descriptor,
would be P90 -- not computed here; min/max already bound the extremes.)
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

# The percentile rank (in the ascending-sorted level distribution) that L90 -- "the
# level exceeded 90% of the time" -- corresponds to. See the module docstring.
_L90_PERCENTILE_RANK = 10.0


@dataclass(frozen=True)
class MinuteLevel:
    """A bounded four-scalar summary of one wall-clock minute of levels. Never audio."""

    minute_start: float  # unix seconds, floored to the minute
    min_dbfs: float
    median_dbfs: float
    max_dbfs: float
    l90_dbfs: float  # level exceeded 90% of the time this minute (P10; see module doc)
    frame_count: int


def percentile(sorted_values: list[float], rank: float) -> float:
    """Linear-interpolation percentile of an ascending-sorted, non-empty list.

    ``rank`` is in [0, 100]. Matches the common "linear" convention (NumPy's default,
    Excel's PERCENTILE.INC): the value at fractional index ``rank/100 * (n - 1)``,
    interpolated between its two bracketing elements. Worked example:
    ``percentile([1,2,...,10], 10) == 1.9`` -- fractional index 0.1 * 9 = 0.9 sits
    9/10 of the way from 1 to 2. Public (not module-private) because both the
    per-minute reduction below and the report's day-level ambient rollup
    (``report/aggregate.py``) need the exact same rule.
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    index = (rank / 100.0) * (n - 1)
    lo = math.floor(index)
    hi = math.ceil(index)
    if lo == hi:
        return sorted_values[int(index)]
    frac = index - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def summarize_minute(levels: list[float], minute_start: float) -> MinuteLevel:
    """Reduce one minute's worth of dBFS readings to the bounded four-scalar summary.

    ``levels`` must be non-empty. This is a pure function -- the streaming buffering
    lives in :class:`MinuteAggregator` below -- so it is directly unit-testable with
    hand-computed inputs.
    """
    ordered = sorted(levels)
    return MinuteLevel(
        minute_start=minute_start,
        min_dbfs=ordered[0],
        median_dbfs=statistics.median(ordered),
        max_dbfs=ordered[-1],
        l90_dbfs=percentile(ordered, _L90_PERCENTILE_RANK),
        frame_count=len(ordered),
    )


class MinuteAggregator:
    """Buffers dBFS readings for the current wall-clock minute; flushes on rollover.

    Feed readings with ``push(t, level)`` in non-decreasing ``t`` order (the same order
    the pipeline already processes frames in). It returns a closed :class:`MinuteLevel`
    exactly when a reading's minute differs from the buffered one -- i.e. once per
    minute boundary crossed, never more. Call :meth:`flush` once at the end of the
    stream to emit the final, possibly-partial minute. At most one minute's worth of
    scalars (not audio, not frames) is ever held in memory.
    """

    def __init__(self, *, bucket_seconds: float = 60.0) -> None:
        if bucket_seconds <= 0:
            raise ValueError("bucket_seconds must be positive")
        self._bucket_seconds = bucket_seconds
        self._minute_start: float | None = None
        self._levels: list[float] = []

    def push(self, t: float, level: float) -> MinuteLevel | None:
        bucket = math.floor(t / self._bucket_seconds) * self._bucket_seconds
        if self._minute_start is None:
            self._minute_start = bucket
            self._levels = [level]
            return None
        if bucket == self._minute_start:
            self._levels.append(level)
            return None
        # Rolled into a new minute: close the previous one, start the new buffer.
        finished = summarize_minute(self._levels, self._minute_start)
        self._minute_start = bucket
        self._levels = [level]
        return finished

    def flush(self) -> MinuteLevel | None:
        """Close and return the current (possibly partial) minute, or None if empty."""
        if self._minute_start is None or not self._levels:
            return None
        finished = summarize_minute(self._levels, self._minute_start)
        self._minute_start = None
        self._levels = []
        return finished
