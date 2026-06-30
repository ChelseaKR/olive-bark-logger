"""Frame sources for the monitor.

A *source* is any iterable of (timestamp, frame) pairs, where a frame is a short
in-memory sequence of float samples in [-1.0, 1.0]. The pipeline pulls one frame,
reduces it to a level, and drops it. Frames are never stored or returned downstream.

This module holds the synthetic source used by tests and the eval (deterministic,
no hardware). The live microphone source lives in capture_live.py and is imported
lazily so the core has no audio-library dependency.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterator, Sequence
from typing import NamedTuple


class LoudRegion(NamedTuple):
    """A labeled span of loud audio within a synthetic session, for eval/tests."""

    start_s: float
    end_s: float
    amplitude: float  # peak sample amplitude in (0, 1]


def _frame(amplitude: float, frame_size: int, phase: float, sample_rate: int) -> list[float]:
    """One frame of a sine tone at the given peak amplitude (in-memory only)."""
    if amplitude <= 0.0:
        return [0.0] * frame_size
    w = 2.0 * math.pi * 440.0 / sample_rate
    return [amplitude * math.sin(phase + w * i) for i in range(frame_size)]


def synthetic_session(
    duration_s: float,
    loud_regions: Sequence[LoudRegion],
    *,
    sample_rate: int = 16000,
    frame_size: int = 1600,
    quiet_amplitude: float = 0.001,
) -> Iterator[tuple[float, list[float]]]:
    """Yield (t, frame) over duration_s, loud inside the labeled regions, quiet elsewhere.

    Timestamps start at 0.0 and advance by frame_size/sample_rate per frame. The
    quiet floor is a tiny non-zero amplitude so quiet readings are realistic dBFS
    values rather than the digital-silence floor.
    """
    frame_dt = frame_size / sample_rate
    n_frames = int(math.ceil(duration_s / frame_dt))
    phase = 0.0
    for i in range(n_frames):
        t = i * frame_dt
        amp = quiet_amplitude
        for region in loud_regions:
            if region.start_s <= t < region.end_s:
                amp = region.amplitude
                break
        yield t, _frame(amp, frame_size, phase, sample_rate)
        phase = (phase + 2.0 * math.pi * 440.0 / sample_rate * frame_size) % (2.0 * math.pi)


def resilient_source(
    make_source: Callable[[], Iterator[tuple[float, list[float]]]],
    *,
    retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[tuple[float, list[float]]]:
    """Wrap a source factory so a device error (e.g. a USB mic unplugged) is retried.

    On failure, re-invokes make_source() with exponential backoff rather than crashing
    the unattended service. Gives up after `retries` consecutive failures so a truly dead
    device surfaces an error instead of looping forever.
    """
    attempt = 0
    while True:
        try:
            yield from make_source()
            return  # source ended normally
        except Exception:
            attempt += 1
            if attempt > retries:
                raise
            sleep(min(max_delay, base_delay * (2 ** (attempt - 1))))
