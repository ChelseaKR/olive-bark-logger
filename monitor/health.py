"""Frame-coverage accounting and a heartbeat file for unattended operation.

"Zero audio stored" is the privacy guarantee; "we processed the frames we were given"
is the *integrity* guarantee that keeps the event counts honest. If frames are dropped
under backpressure, that has to be visible — silently missing half the frames would make
the counts wrong while still looking clean. CaptureStats tracks seen vs dropped, and the
heartbeat file lets a watchdog (systemd, cron) confirm the monitor is alive and keeping up.

Everything here is local: the heartbeat is a small JSON file written atomically. No audio,
no network.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CaptureStats:
    """Mutable frame counters shared between the capture source and the pipeline."""

    frames_seen: int = 0
    frames_dropped: int = 0

    @property
    def coverage(self) -> float:
        """Fraction of offered frames actually processed (1.0 if none were dropped)."""
        total = self.frames_seen + self.frames_dropped
        return 1.0 if total == 0 else self.frames_seen / total


def write_health(path: str | Path, payload: dict[str, object]) -> None:
    """Atomically write the heartbeat JSON (temp file + os.replace), so a reader never
    sees a half-written file and a crash mid-write cannot corrupt it."""
    target = Path(path)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, target)
