"""Clock-integrity guard: detect wall-clock vs monotonic-clock divergence during capture.

On a Raspberry Pi with no real-time clock the wall clock can lurch — forward when NTP
finally syncs after boot, or in either direction across a suspend/resume. Event
timestamps are wall time, so an undisclosed jump would silently smear the timeline. The
monotonic clock never jumps, so comparing the two exposes the lurch.

ClockGuard tracks both clocks from a baseline. On each check it computes the *drift* —
how far wall time has moved relative to monotonic time since the last baseline. Drift
beyond a tolerance is a clock jump: we emit an anomaly record (wall time expected vs
observed, signed delta, direction) and re-baseline so a single jump is reported once, not
on every subsequent check.

Everything here is pure and clock-injected: `check` takes the current wall and monotonic
readings as arguments, so tests drive it with synthetic clocks and no real time passes.
No audio, no I/O.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# Anomaly kinds. Classification stays deliberately simple: which way wall time jumped.
FORWARD_JUMP = "forward-jump"
BACKWARD_JUMP = "backward-jump"


@dataclass(frozen=True)
class ClockAnomalyRecord:
    """One detected clock jump. Metadata only — five numbers and a direction string."""

    kind: str
    wall_before: float  # wall time expected from monotonic progression since baseline
    wall_after: float  # wall time actually observed at the check
    delta: float  # wall_after - wall_before (signed drift, seconds)
    detected_at: float  # observed wall time at detection


class ClockGuard:
    """Track wall vs monotonic time and flag divergence beyond a tolerance.

    The baseline is captured at construction from the injected (or real) clocks. Call
    ``check(now_wall, now_mono)`` periodically — per event and/or heartbeat. It returns a
    ``ClockAnomalyRecord`` when the drift since the last baseline exceeds the tolerance,
    otherwise ``None``. After a detection it re-baselines to the current readings.
    """

    def __init__(
        self,
        *,
        wall0: float | None = None,
        mono0: float | None = None,
        tolerance_s: float = 2.0,
    ) -> None:
        self._wall0 = time.time() if wall0 is None else wall0
        self._mono0 = time.monotonic() if mono0 is None else mono0
        self.tolerance_s = tolerance_s

    def check(self, now_wall: float, now_mono: float) -> ClockAnomalyRecord | None:
        """Compare wall and monotonic progress since the baseline; flag a jump if large.

        drift = (wall elapsed) - (monotonic elapsed). A steady clock keeps drift ~0. A
        forward wall jump makes drift positive; a backward jump makes it negative.
        """
        wall_elapsed = now_wall - self._wall0
        mono_elapsed = now_mono - self._mono0
        drift = wall_elapsed - mono_elapsed
        if abs(drift) <= self.tolerance_s:
            return None
        # Wall time we would expect if only the monotonic clock had advanced.
        wall_before = self._wall0 + mono_elapsed
        anomaly = ClockAnomalyRecord(
            kind=FORWARD_JUMP if drift > 0 else BACKWARD_JUMP,
            wall_before=wall_before,
            wall_after=now_wall,
            delta=drift,
            detected_at=now_wall,
        )
        # Re-baseline so this jump is reported exactly once.
        self._wall0 = now_wall
        self._mono0 = now_mono
        return anomaly
