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
