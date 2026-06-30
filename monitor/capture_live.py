"""Live microphone frame source (Raspberry Pi / laptop).

Kept separate from the core so installing audio libraries is optional and so the
no-audio static gate can assert that the *only* thing this module does with samples
is hand them to the level computer. There is deliberately no API here to write a
frame to disk or send it anywhere: the InputStream callback's buffer is converted
to a plain Python list, yielded for level computation, and then dropped.

Requires the optional `live` extra: pip install -e ".[live]"
"""

from __future__ import annotations

import queue
import time
from collections.abc import Iterator

from monitor.health import CaptureStats


def live_source(
    sample_rate: int = 16000,
    frame_size: int = 1600,
    stats: CaptureStats | None = None,
) -> Iterator[tuple[float, list[float]]]:  # pragma: no cover - requires hardware
    """Yield (t, frame) from the default input device. Frames are never persisted.

    If a CaptureStats is given, frames dropped under backpressure are counted so the
    report can disclose frame coverage instead of silently undercounting events.
    """
    try:
        import sounddevice as sd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Live capture needs the 'live' extra: pip install -e \".[live]\""
        ) from exc

    frames: queue.Queue[list[float]] = queue.Queue(maxsize=8)

    def _callback(indata, _frames, _time, _status):  # type: ignore[no-untyped-def]
        # indata is a buffer of floats for one frame. Copy to a list (in memory),
        # enqueue for level computation, and let the buffer be reused. Nothing is
        # written to disk or sent over the network — there is no code path that could.
        mono = [float(indata[i, 0]) for i in range(len(indata))]
        # Drop a frame under backpressure rather than buffer audio; count the drop.
        try:
            frames.put_nowait(mono)
        except queue.Full:
            if stats is not None:
                stats.frames_dropped += 1

    with sd.InputStream(
        samplerate=sample_rate,
        blocksize=frame_size,
        channels=1,
        dtype="float32",
        callback=_callback,
    ):
        while True:
            frame = frames.get()
            yield time.time(), frame
