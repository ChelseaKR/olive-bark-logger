"""Shared fixtures and path setup so tests import the source packages directly."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACKAGE_DIRS = [ROOT / "monitor", ROOT / "store", ROOT / "report"]


def source_files() -> list[Path]:
    """All first-party Python source files (the surface the guardrail gates scan)."""
    files: list[Path] = []
    for pkg in PACKAGE_DIRS:
        files.extend(sorted(pkg.glob("*.py")))
    return files
