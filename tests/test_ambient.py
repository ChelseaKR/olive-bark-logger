"""Streaming per-minute ambient level aggregates (EXP-01): pure math, no hardware.

MinuteAggregator/summarize_minute never touch audio -- they consume the same dBFS
scalars the detector already sees -- so these tests drive them directly with
hand-computed values, the same way tests/test_detector.py exercises the Detector
state machine without any capture source.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from monitor.ambient import MinuteAggregator, MinuteLevel, percentile, summarize_minute


def test_percentile_matches_hand_computed_linear_interpolation():
    # Ascending 1..10; P10 sits 0.9 of the way from index 0 (1) to index 1 (2).
    values = [float(v) for v in range(1, 11)]
    assert percentile(values, 10.0) == 1.9
    # P50 of an even-length list averages the two middle elements (matches median).
    assert percentile(values, 50.0) == 5.5
    # The endpoints are exact.
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 100.0) == 10.0


def test_percentile_single_value():
    assert percentile([-42.0], 10.0) == -42.0
    assert percentile([-42.0], 90.0) == -42.0


def test_summarize_minute_basic():
    # Ten readings, evenly spread -35..-26; min/median/max are exact, L90 (P10) is the
    # same worked example as the percentile test, shifted onto this scale.
    levels = [float(v) for v in range(-35, -25)]  # -35..-26
    m = summarize_minute(levels, minute_start=600.0)
    assert isinstance(m, MinuteLevel)
    assert m.minute_start == 600.0
    assert m.min_dbfs == -35.0
    assert m.max_dbfs == -26.0
    assert m.median_dbfs == -30.5
    assert m.l90_dbfs == -34.1  # -35 + 0.9
    assert m.frame_count == 10


def test_summarize_minute_single_reading():
    m = summarize_minute([-40.0], minute_start=0.0)
    assert (m.min_dbfs, m.median_dbfs, m.max_dbfs, m.l90_dbfs) == (-40.0, -40.0, -40.0, -40.0)
    assert m.frame_count == 1


def test_summarize_minute_unsorted_input_is_sorted_first():
    levels = [-10.0, -40.0, -25.0]
    m = summarize_minute(levels, minute_start=0.0)
    assert m.min_dbfs == -40.0
    assert m.max_dbfs == -10.0
    assert m.median_dbfs == -25.0


# -- MinuteAggregator: streaming buffering + minute-boundary rollover --------------


def test_aggregator_buffers_within_one_minute_and_returns_none():
    agg = MinuteAggregator()
    assert agg.push(0.0, -30.0) is None
    assert agg.push(30.0, -20.0) is None
    assert agg.push(59.9, -40.0) is None  # still inside minute 0


def test_aggregator_emits_on_minute_rollover():
    agg = MinuteAggregator()
    agg.push(0.0, -30.0)
    agg.push(30.0, -20.0)
    finished = agg.push(60.0, -25.0)  # crosses into minute 1
    assert finished is not None
    assert finished.minute_start == 0.0
    assert finished.frame_count == 2
    assert finished.min_dbfs == -30.0
    assert finished.max_dbfs == -20.0


def test_aggregator_only_emits_once_per_boundary_crossed():
    agg = MinuteAggregator()
    results = [agg.push(t, -30.0) for t in (0.0, 10.0, 20.0, 60.0, 70.0, 120.0)]
    # Only the two readings that crossed a boundary (60.0 -> minute 1, 120.0 -> minute 2)
    # produce a closed minute; the rest buffer silently.
    closed = [r for r in results if r is not None]
    assert [c.minute_start for c in closed] == [0.0, 60.0]


def test_aggregator_flush_emits_partial_final_minute():
    agg = MinuteAggregator()
    agg.push(0.0, -30.0)
    agg.push(10.0, -20.0)
    finished = agg.flush()
    assert finished is not None
    assert finished.minute_start == 0.0
    assert finished.frame_count == 2


def test_aggregator_flush_on_empty_stream_returns_none():
    assert MinuteAggregator().flush() is None


def test_aggregator_flush_after_rollover_flush_is_idempotent_empty():
    agg = MinuteAggregator()
    agg.push(0.0, -30.0)
    agg.push(60.0, -25.0)  # closes minute 0
    first = agg.flush()  # closes minute 1 (the only buffered one)
    assert first is not None and first.minute_start == 60.0
    assert agg.flush() is None  # nothing left to flush


def test_aggregator_rejects_non_positive_bucket_seconds():
    with pytest.raises(ValueError):
        MinuteAggregator(bucket_seconds=0.0)


# -- Property: the four scalars always respect min <= L90 <= median <= max ---------


@given(
    st.lists(
        st.floats(min_value=-120.0, max_value=0.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=200,
    )
)
def test_summary_scalars_are_always_ordered(levels: list[float]):
    m = summarize_minute(levels, minute_start=0.0)
    assert m.min_dbfs <= m.l90_dbfs <= m.median_dbfs <= m.max_dbfs
    assert m.frame_count == len(levels)
    assert m.min_dbfs == min(levels)
    assert m.max_dbfs == max(levels)
