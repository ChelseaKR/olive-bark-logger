"""On-device noise monitor: capture frames, compute levels in memory, detect events.

Hard design gate: nothing in this package writes audio bytes to disk or sends them
over a network. Capture sources yield short in-memory frames to the level computer,
which reduces each frame to a single number; the frame is then dropped. Only derived
levels and event metadata ever leave the pipeline. See tests/test_no_audio.py.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth is `pyproject.toml`'s `[project].version` (REL-02);
    # this reads the installed package metadata instead of hand-copying the string.
    __version__ = version("olive-bark-logger")
except PackageNotFoundError:  # pragma: no cover - only when run from an uninstalled checkout
    __version__ = "0.0.0+unknown"

__all__ = ["__version__", "config", "detector", "health", "level"]
