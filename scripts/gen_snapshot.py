"""Regenerate the committed report snapshot. Run via `make snapshot`."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_report_snapshot import GOLDEN, fixture_html  # noqa: E402

GOLDEN.parent.mkdir(parents=True, exist_ok=True)
GOLDEN.write_text(fixture_html(), encoding="utf-8")
print(f"Wrote {GOLDEN.relative_to(ROOT)} ({GOLDEN.stat().st_size} bytes).")
