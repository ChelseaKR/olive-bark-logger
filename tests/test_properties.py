"""Property-based tests for the level math and detector invariants (Hypothesis).

These assert properties that must hold for *all* inputs, not just chosen examples —
a stronger maintainability net against regressions than example tests alone.
"""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st
from monitor.detector import Detector
from monitor.level import SILENCE_FLOOR_DBFS, dbfs

amplitudes = st.floats(min_value=1e-6, max_value=1.0, allow_nan=False, allow_infinity=False)
levels = st.floats(min_value=-120.0, max_value=0.0, allow_nan=False, allow_infinity=False)


@given(amp=amplitudes, n=st.integers(min_value=1, max_value=64))
def test_dbfs_matches_constant_amplitude_formula(amp, n):
    # A constant-|amp| frame has RMS = amp, so dBFS = 20*log10(amp) (above the floor).
    frame = [amp] * n
    expected = max(SILENCE_FLOOR_DBFS, 20 * math.log10(amp))
    assert abs(dbfs(frame) - expected) < 1e-6


@given(amp=amplitudes, offset=st.floats(min_value=-50, max_value=120))
def test_dbfs_never_below_floor_plus_offset(amp, offset):
    assert dbfs([amp], calibration_offset=offset) >= SILENCE_FLOOR_DBFS + offset - 1e-9


@given(a=amplitudes, b=amplitudes)
def test_dbfs_monotonic_in_amplitude(a, b):
    if a < b:
        assert dbfs([a]) <= dbfs([b]) + 1e-9


@given(
    threshold=st.floats(min_value=-80, max_value=-10),
    seq=st.lists(st.tuples(st.floats(0, 100), levels), min_size=0, max_size=50),
)
def test_emitted_events_respect_invariants(threshold, seq):
    # Times must be non-decreasing for a real stream; sort by time.
    readings = sorted(seq, key=lambda x: x[0])
    d = Detector(threshold_dbfs=threshold, min_duration_s=0.5, debounce_s=1.0)
    events = []
    for t, level in readings:
        ev = d.push(t, level)
        if ev:
            events.append(ev)
    final = d.flush()
    if final:
        events.append(final)
    for ev in events:
        assert ev.duration >= 0.5 - 1e-9  # min-duration honored
        assert ev.end >= ev.start
        assert ev.avg_level <= ev.peak_level + 1e-9
        assert ev.peak_level >= threshold  # peak came from a loud reading
