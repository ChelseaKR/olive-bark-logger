"""Reduce an in-memory audio frame to a single sound level in dBFS.

This is the only place raw samples are touched. A frame is a sequence of float
samples in [-1.0, 1.0]; we compute its RMS and convert to decibels relative to
full scale (dBFS). The frame is never copied out, stored, or returned — callers
receive a float, not the samples.

dBFS is *relative*: 0 dBFS is a full-scale sine. It is not absolute SPL (dB) unless
a calibration offset measured against a reference is applied. The report states this
limitation explicitly; see report/render.py and docs/audits/methodology-and-limitations.md.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

# Floor for digital silence. RMS of 0 is -inf dB; we clamp so downstream math and
# charts stay finite. -120 dBFS is well below any real room noise floor.
SILENCE_FLOOR_DBFS: float = -120.0


def rms(frame: Iterable[float]) -> float:
    """Root-mean-square amplitude of a frame. 0.0 for an empty or silent frame."""
    total = 0.0
    count = 0
    for sample in frame:
        total += sample * sample
        count += 1
    if count == 0:
        return 0.0
    return math.sqrt(total / count)


def dbfs(frame: Iterable[float], *, calibration_offset: float = 0.0) -> float:
    """Frame level in dBFS, with an optional calibration offset added.

    The offset (in dB) shifts the relative dBFS reading toward an approximate SPL
    when the device has been calibrated against a reference meter. With offset 0.0
    the value is purely relative. Result is clamped at SILENCE_FLOOR_DBFS.
    """
    amplitude = rms(frame)
    if amplitude <= 0.0:
        return SILENCE_FLOOR_DBFS + calibration_offset
    level = 20.0 * math.log10(amplitude)
    if level < SILENCE_FLOOR_DBFS:
        level = SILENCE_FLOOR_DBFS
    return level + calibration_offset
