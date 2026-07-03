"""Event detection: threshold, min-duration filtering, debounce, flush."""

from __future__ import annotations

import pytest
from monitor.detector import Detector


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


def test_negative_params_rejected():
    with pytest.raises(ValueError):
        Detector(threshold_dbfs=-30, min_duration_s=-1, debounce_s=0)


def test_single_loud_frame_is_filtered_by_min_duration():
    d = Detector(threshold_dbfs=-30, min_duration_s=0.5, debounce_s=0.2)
    # One loud reading at t=0, then quiet -> duration 0 < 0.5 -> no event.
    events = _run(d, [(0.0, -10), (0.3, -60), (0.6, -60)])
    assert events == []


def test_sustained_loud_makes_one_event():
    d = Detector(threshold_dbfs=-30, min_duration_s=0.5, debounce_s=0.2)
    readings = [(t / 10, -10) for t in range(0, 11)]  # 0.0..1.0s loud
    readings.append((2.0, -60))  # quiet, beyond debounce -> close
    events = _run(d, readings)
    assert len(events) == 1
    ev = events[0]
    assert ev.start == 0.0 and ev.end == 1.0
    assert abs(ev.duration - 1.0) < 1e-9
    assert ev.peak_level == -10
    assert ev.avg_level == -10


def test_debounce_bridges_brief_dip():
    d = Detector(threshold_dbfs=-30, min_duration_s=0.3, debounce_s=1.0)
    readings = [
        (0.0, -10),
        (0.5, -10),
        (1.0, -60),  # dip, but within 1.0s debounce
        (1.5, -10),  # back loud -> still same event
        (2.0, -10),
        (4.0, -60),  # quiet beyond debounce -> close
    ]
    events = _run(d, readings)
    assert len(events) == 1
    assert events[0].start == 0.0
    assert events[0].end == 2.0


def test_dip_longer_than_debounce_splits_events():
    d = Detector(threshold_dbfs=-30, min_duration_s=0.3, debounce_s=0.5)
    readings = [
        (0.0, -10),
        (0.5, -10),  # event A: 0.0..0.5
        (2.0, -60),  # 1.5s gap > debounce -> closes A
        (3.0, -10),
        (3.5, -10),  # event B: 3.0..3.5
        (6.0, -60),  # closes B
    ]
    events = _run(d, readings)
    assert len(events) == 2
    assert events[0].start == 0.0 and events[0].end == 0.5
    assert events[1].start == 3.0 and events[1].end == 3.5


def test_peak_and_avg_over_loud_readings_only():
    d = Detector(threshold_dbfs=-30, min_duration_s=0.1, debounce_s=1.0)
    readings = [(0.0, -20), (0.5, -10), (1.0, -25), (3.0, -60)]
    events = _run(d, readings)
    assert len(events) == 1
    ev = events[0]
    assert ev.peak_level == -10
    assert abs(ev.avg_level - ((-20 + -10 + -25) / 3)) < 1e-9


def test_flush_closes_open_event_at_end_of_stream():
    d = Detector(threshold_dbfs=-30, min_duration_s=0.3, debounce_s=1.0)
    events = _run(d, [(0.0, -10), (0.5, -10), (1.0, -10)])  # never goes quiet
    assert len(events) == 1
    assert events[0].end == 1.0


# -- envelope anatomy (bounded per-event shape descriptors) -------------------------


def test_anatomy_long_drone_is_one_unbroken_loud_run():
    """A steady drone well above threshold: rise ~0, one run ~ duration, lots of loud6."""
    d = Detector(threshold_dbfs=-30, min_duration_s=0.5, debounce_s=0.5)
    # -10 dBFS >= threshold+6 (-24), sampled every 0.1 s across a full second.
    readings = [(t / 10, -10.0) for t in range(0, 11)]  # 0.0..1.0 s loud
    readings.append((2.0, -60.0))  # quiet beyond debounce -> close
    events = _run(d, readings)
    assert len(events) == 1
    ev = events[0]
    assert ev.rise_time_s == 0.0  # already at/above threshold+6 on the opening frame
    assert abs(ev.loud6_s - 1.0) < 1e-9  # essentially the whole event is well above +6
    assert abs(ev.longest_run_s - 1.0) < 1e-9  # one continuous run spanning the drone


def test_anatomy_short_spikes_with_debounce_gaps_have_tiny_runs_and_loud6():
    """Many isolated spikes bridged by debounce: each run is momentary; loud6 ~ 0."""
    d = Detector(threshold_dbfs=-30, min_duration_s=0.1, debounce_s=2.0)
    readings = [
        (0.0, -10.0),  # spike (opens)
        (0.5, -60.0),  # dip ends the run, debounce keeps event open
        (1.0, -10.0),  # spike
        (1.5, -60.0),
        (2.0, -10.0),  # spike
        (2.5, -60.0),
        (3.0, -10.0),  # spike
        (5.5, -60.0),  # quiet beyond debounce -> close
    ]
    events = _run(d, readings)
    assert len(events) == 1
    ev = events[0]
    # Each spike is a single instantaneous reading, so no run has any span.
    assert ev.longest_run_s == 0.0
    # No interval both starts and stays above threshold, so no loud6 time accrues.
    assert ev.loud6_s == 0.0
    assert ev.rise_time_s == 0.0  # the first spike is itself already above threshold+6


def test_anatomy_never_reaching_threshold_plus_6_has_none_rise_time():
    """An event that stays above threshold but never above +6 dB has rise_time None."""
    d = Detector(threshold_dbfs=-30, min_duration_s=0.3, debounce_s=1.0)
    # -28 dBFS is above threshold (-30) but below threshold+6 (-24).
    readings = [(0.0, -28.0), (0.5, -28.0), (1.0, -28.0), (3.0, -60.0)]
    events = _run(d, readings)
    assert len(events) == 1
    ev = events[0]
    assert ev.rise_time_s is None  # +6 dB never reached
    assert ev.loud6_s == 0.0
    assert abs(ev.longest_run_s - 1.0) < 1e-9  # still one unbroken above-threshold run


def test_anatomy_rise_time_measures_delay_to_first_loud6_reading():
    """Rise time is the gap from event start to the first reading at/above +6 dB."""
    d = Detector(threshold_dbfs=-30, min_duration_s=0.3, debounce_s=1.0)
    readings = [
        (0.0, -28.0),  # above threshold, below +6
        (0.5, -26.0),  # still below +6
        (0.8, -10.0),  # first reading at/above +6 -> rise_time = 0.8
        (1.2, -10.0),
        (3.0, -60.0),
    ]
    events = _run(d, readings)
    assert len(events) == 1
    assert abs(events[0].rise_time_s - 0.8) < 1e-9
