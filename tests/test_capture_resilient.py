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
