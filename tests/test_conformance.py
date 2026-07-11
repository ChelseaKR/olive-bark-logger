"""Cross-implementation conformance: the Python detector must reproduce every
golden vector in spec/detector/. The same vectors are replayed against the PWA
detector in pwa/conformance.test.mjs, so the two ports cannot silently drift.

Changing detection semantics on either side means changing a vector on purpose
(see spec/SEMANTICS.md) — a vector mismatch here is the drift being caught.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from monitor.detector import Detector

SPEC_DIR = Path(__file__).resolve().parent.parent / "spec" / "detector"
VECTOR_FILES = sorted(SPEC_DIR.glob("*.json"))


def _run(detector, readings):
    events = []
    for t, level in readings:
        ev = detector.push(t, level)
        if ev:
            events.append(ev)
    final = detector.flush()
    if final:
        events.append(final)
    return events


def test_spec_directory_is_populated():
    # An empty or moved spec/ dir must fail loudly rather than trivially pass.
    assert VECTOR_FILES, f"no conformance vectors found under {SPEC_DIR}"


@pytest.mark.parametrize("vector_file", VECTOR_FILES, ids=lambda p: p.stem)
def test_detector_matches_vector(vector_file: Path):
    vec = json.loads(vector_file.read_text())
    p = vec["params"]
    d = Detector(
        threshold_dbfs=p["threshold_dbfs"],
        min_duration_s=p["min_duration_s"],
        debounce_s=p["debounce_s"],
    )
    events = _run(d, vec["readings"])
    expected = vec["expected_events"]

    assert len(events) == len(expected), (
        f"{vec['name']}: got {len(events)} events, expected {len(expected)}"
    )
    for got, exp in zip(events, expected):
        assert got.start == pytest.approx(exp["start"], abs=1e-9)
        assert got.end == pytest.approx(exp["end"], abs=1e-9)
        assert got.duration == pytest.approx(exp["duration"], abs=1e-9)
        assert got.peak_level == pytest.approx(exp["peak_level"], abs=1e-9)
        assert got.avg_level == pytest.approx(exp["avg_level"], abs=1e-9)
