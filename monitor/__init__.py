"""On-device noise monitor: capture frames, compute levels in memory, detect events.

Hard design gate: nothing in this package writes audio bytes to disk or sends them
over a network. Capture sources yield short in-memory frames to the level computer,
which reduces each frame to a single number; the frame is then dropped. Only derived
levels and event metadata ever leave the pipeline. See tests/test_no_audio.py.
"""

__version__ = "0.1.0"

__all__ = ["__version__", "level", "detector", "config", "health"]
