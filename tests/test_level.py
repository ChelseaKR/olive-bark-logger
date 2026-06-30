"""Level math: RMS, dBFS conversion, silence floor, calibration offset."""

from __future__ import annotations

import math

from monitor.level import SILENCE_FLOOR_DBFS, dbfs, rms


def test_rms_of_empty_is_zero():
    assert rms([]) == 0.0


def test_rms_of_constant():
    assert rms([0.5, 0.5, 0.5]) == 0.5


def test_rms_of_sine_is_amplitude_over_sqrt2():
    samples = [math.sin(2 * math.pi * i / 100) for i in range(100)]
    assert rms(samples) == 0.7071067811865476 or abs(rms(samples) - 1 / math.sqrt(2)) < 1e-3


def test_full_scale_is_zero_dbfs():
    # A constant at amplitude 1.0 has RMS 1.0 -> 0 dBFS.
    assert dbfs([1.0, 1.0, 1.0]) == 0.0


def test_half_amplitude_is_about_minus_6_dbfs():
    assert abs(dbfs([0.5, 0.5, 0.5]) - (-6.0206)) < 1e-3


def test_silence_clamps_to_floor():
    assert dbfs([0.0, 0.0]) == SILENCE_FLOOR_DBFS
    assert dbfs([]) == SILENCE_FLOOR_DBFS


def test_calibration_offset_is_added():
    base = dbfs([0.5, 0.5])
    assert abs(dbfs([0.5, 0.5], calibration_offset=10.0) - (base + 10.0)) < 1e-9


def test_very_quiet_clamps_to_floor_not_below():
    # A signal far below the floor should clamp, then have the offset applied.
    assert dbfs([1e-9], calibration_offset=0.0) == SILENCE_FLOOR_DBFS
