"""Coarse, in-memory frame features for optional bark-like/ambient tagging.

These are computed from the same in-memory frame the level computer sees and are then
discarded with it — no audio is stored. The point is a *coarse* hint (is this a sharp,
broadband transient like a bark, or low, steady ambient like a fridge hum?), never
speech content or identification. The only thing persisted is the resulting short tag.

Zero-crossing rate (ZCR) is a cheap, dependency-free proxy: barks are broadband and
cross zero often; low hums cross rarely. It is deliberately crude and the report frames
any tag as a hint, not a fact.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

BARK_LIKE = "bark-like"
AMBIENT = "ambient"


def zero_crossing_rate(frame: Sequence[float]) -> float:
    """Fraction of adjacent sample pairs that change sign. 0.0 for < 2 samples."""
    if len(frame) < 2:
        return 0.0
    crossings = 0
    prev = frame[0]
    for sample in frame[1:]:
        if (sample >= 0.0) != (prev >= 0.0):
            crossings += 1
        prev = sample
    return crossings / (len(frame) - 1)


def classify(mean_zcr: float, *, zcr_threshold: float = 0.10) -> str:
    """Map a mean zero-crossing rate to a coarse tag."""
    return BARK_LIKE if mean_zcr >= zcr_threshold else AMBIENT


class FeatureWindow:
    """The bounded per-frame feature buffer behind optional event tagging.

    Tagging classifies a closing event by the mean zero-crossing rate over *its own*
    time window, so the pipeline has to keep `(timestamp, zcr)` pairs for frames that
    might still turn out to belong to an open event. Nothing else, and nothing longer.

    The bound is exact rather than a guessed retention horizon, because the detector
    already knows it: while an event is open, frames before its start can never be part
    of it or of any later event; when no event is open, *every* held frame is
    unreachable, since the next event can only begin at a future reading. So the buffer
    is at most one event long, and empty the rest of the time -- which is what
    `run_pipeline` claimed in writing before issue #63.

    What it claimed and what it did had diverged. The buffer was a bare list pruned only
    inside `if event is not None:`, i.e. only when an event *closed*. Through a quiet
    stretch -- a night, a weekend away, any span with nothing crossing the threshold --
    that branch never ran and the list grew by one entry per frame, without limit. At
    the default 1600-sample frame and 16 kHz rate that is 10 entries a second, ~864,000
    a day, on a Raspberry Pi expected to run for weeks under `Restart=always`. The
    quietest installs leaked the most.

    Numbers only, and no frame is retained: `zero_crossing_rate` reduces each frame to a
    single float before anything reaches this buffer, so the no-audio guarantee is
    untouched by what is held here.
    """

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: deque[tuple[float, float]] = deque()

    def __len__(self) -> int:
        return len(self._entries)

    def append(self, t: float, zcr: float) -> None:
        """Record one frame's zero-crossing rate at time `t`."""
        self._entries.append((t, zcr))

    def prune(self, active_since: float | None) -> None:
        """Drop every entry that can no longer belong to any event.

        `active_since` is :attr:`monitor.detector.Detector.active_since` -- the open
        event's start timestamp, or None when no event is open. Call it once per frame:
        the whole defect was a prune that ran only on the rare path.

        Amortized O(1). Entries are appended in timestamp order, so expiry is a
        `popleft` loop rather than a rebuild; rebuilding the buffer on every frame would
        make a single long event quadratic in its own length, which on a sustained drone
        is its own kind of unbounded.
        """
        if active_since is None:
            self._entries.clear()
            return
        entries = self._entries
        while entries and entries[0][0] < active_since:
            entries.popleft()

    def mean_over(self, start: float, end: float) -> float | None:
        """Mean zero-crossing rate over the inclusive window, or None if it is empty.

        None means "no frame feature covers this event", which is a real state (tagging
        switched on mid-event, or an event reconstructed from a source that skipped
        frames) and must stay distinguishable from a computed rate of 0.0 -- the caller
        leaves `coarse_tag` unset rather than classifying an absence.
        """
        window = [z for (t, z) in self._entries if start <= t <= end]
        if not window:
            return None
        return sum(window) / len(window)
