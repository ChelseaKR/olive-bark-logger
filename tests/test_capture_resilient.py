"""resilient_source retries a failing capture source instead of crashing."""

from __future__ import annotations

import pytest
from monitor.capture import resilient_source


def test_retries_then_succeeds():
    calls = {"n": 0}
    delays: list[float] = []

    def make_source():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("device busy")
        yield (0.0, [0.1])
        yield (0.1, [0.2])

    out = list(resilient_source(make_source, sleep=delays.append))
    assert out == [(0.0, [0.1]), (0.1, [0.2])]
    assert calls["n"] == 3
    assert delays == [1.0, 2.0]  # exponential backoff before each retry


def test_gives_up_after_retries():
    def make_source():
        raise OSError("device gone")
        yield  # pragma: no cover - unreachable, makes this a generator

    with pytest.raises(OSError, match="device gone"):
        list(resilient_source(make_source, retries=2, sleep=lambda _: None))


def test_backoff_is_capped():
    delays: list[float] = []
    calls = {"n": 0}

    def make_source():
        calls["n"] += 1
        if calls["n"] <= 6:
            raise OSError("flaky")
        yield (0.0, [0.0])

    list(resilient_source(make_source, retries=10, max_delay=5.0, sleep=delays.append))
    assert max(delays) == 5.0  # 1,2,4,5,5,5 -> capped at max_delay


def test_recovered_failures_do_not_accumulate_toward_retry_limit():
    """Progress between outages makes each later failure a new retry series."""
    calls = {"n": 0}
    delays: list[float] = []

    def make_source():
        calls["n"] += 1
        yield (float(calls["n"]), [0.1])
        if calls["n"] < 4:
            raise OSError("intermittent disconnect")

    out = list(resilient_source(make_source, retries=1, sleep=delays.append))

    assert out == [
        (1.0, [0.1]),
        (2.0, [0.1]),
        (3.0, [0.1]),
        (4.0, [0.1]),
    ]
    assert delays == [1.0, 1.0, 1.0]


class _FakeClock:
    """A monotonic fake wall clock so gap spans are asserted without real time."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


def test_on_gap_reports_outage_span_and_reason():
    clock = _FakeClock()
    calls = {"n": 0}
    gaps: list[tuple[float, float, str]] = []

    def make_source():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("device busy")
        yield (0.0, [0.1])
        yield (0.1, [0.2])

    out = list(
        resilient_source(
            make_source,
            sleep=lambda _: None,
            on_gap=lambda s, e, r: gaps.append((s, e, r)),
            clock=clock,
        )
    )
    assert out == [(0.0, [0.1]), (0.1, [0.2])]
    # Exactly one gap, spanning first-failure to recovery, tagged device-error.
    assert len(gaps) == 1
    start, end, reason = gaps[0]
    assert reason == "device-error"
    assert start < end  # outage began before it recovered


def test_on_gap_emitted_when_retries_exhausted():
    clock = _FakeClock()
    gaps: list[tuple[float, float, str]] = []

    def make_source():
        raise OSError("device gone")
        yield  # pragma: no cover - unreachable, makes this a generator

    with pytest.raises(OSError, match="device gone"):
        list(
            resilient_source(
                make_source,
                retries=2,
                sleep=lambda _: None,
                on_gap=lambda s, e, r: gaps.append((s, e, r)),
                clock=clock,
            )
        )
    # A single gap is still recorded for the outage even though we gave up.
    assert len(gaps) == 1
    start, end, reason = gaps[0]
    assert reason == "device-error" and start < end
