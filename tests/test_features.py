"""Coarse feature extraction and optional event tagging in the pipeline."""

from __future__ import annotations

from monitor.config import Config
from monitor.features import AMBIENT, BARK_LIKE, classify, zero_crossing_rate
from monitor.level import dbfs
from monitor.service import run_pipeline


def test_zcr_constant_sign_is_zero():
    assert zero_crossing_rate([0.2, 0.3, 0.4]) == 0.0


def test_zcr_alternating_is_one():
    assert zero_crossing_rate([0.3, -0.3, 0.3, -0.3]) == 1.0


def test_zcr_short_frame():
    assert zero_crossing_rate([0.1]) == 0.0
    assert zero_crossing_rate([]) == 0.0


def test_classify_thresholds():
    assert classify(0.5) == BARK_LIKE
    assert classify(0.0) == AMBIENT
    assert classify(0.10) == BARK_LIKE  # boundary is inclusive


def _loud(alternating: bool, n: int = 10) -> list[float]:
    if alternating:
        return [0.3 if i % 2 == 0 else -0.3 for i in range(n)]  # high ZCR -> bark-like
    return [0.3] * n  # zero ZCR -> ambient


def _source(frames: list[tuple[float, list[float]]]):
    yield from frames


def _run(loud_frame: list[float]):
    config = Config(threshold_dbfs=-35.0, min_duration_s=0.2, debounce_s=0.3, tagging=True)
    quiet = [0.0] * 10
    frames = [(i * 0.1, loud_frame) for i in range(6)]  # 0.0..0.5 loud
    frames.append((1.0, quiet))  # gap > debounce closes the event
    return list(run_pipeline(_source(frames), config))


def test_pipeline_tags_bark_like():
    events = _run(_loud(alternating=True))
    assert len(events) == 1
    assert events[0].coarse_tag == BARK_LIKE


def test_pipeline_tags_ambient():
    events = _run(_loud(alternating=False))
    assert len(events) == 1
    assert events[0].coarse_tag == AMBIENT


def test_tagging_off_leaves_tag_none():
    config = Config(threshold_dbfs=-35.0, min_duration_s=0.2, debounce_s=0.3, tagging=False)
    frames = [(i * 0.1, _loud(True)) for i in range(6)]
    frames.append((1.0, [0.0] * 10))
    events = list(run_pipeline(_source(frames), config))
    assert events[0].coarse_tag is None


# --- The feature buffer is bounded (issue #63) ---------------------------------------
#
# `run_pipeline` promised in writing that its (t, zcr) buffer "never holds more than one
# event's worth of frame features". It pruned only inside `if event is not None:`, so a
# stretch with no event closing -- a quiet night, a weekend away -- never pruned at all
# and the buffer grew by one entry per frame forever. The tests above never caught it
# because every one of them drives a single short event.
#
# The gate below watches the buffer's peak length through a long quiet stretch. The
# canary after it re-runs the same measurement against the pre-#63 pruning rule and
# proves the gate goes red, on the pattern tests/gates.py uses: the check that clears
# the tree is shown flagging a planted defect.

from monitor import service  # noqa: E402
from monitor.detector import Detector  # noqa: E402
from monitor.features import FeatureWindow  # noqa: E402

QUIET_FRAMES = 2000


def _quiet_source(n: int):
    """`n` frames at roughly -60 dBFS: nothing ever crosses the threshold."""
    for i in range(n):
        yield i * 0.1, [0.001] * 160


def _peak_buffer_len(monkeypatch, window_cls, frames: int = QUIET_FRAMES) -> int:
    """Run the pipeline over a quiet stretch, returning the buffer's high-water mark."""
    seen: list[int] = [0]

    class Recording(window_cls):  # type: ignore[valid-type, misc]
        def append(self, t: float, zcr: float) -> None:
            super().append(t, zcr)
            seen[0] = max(seen[0], len(self))

    monkeypatch.setattr(service, "FeatureWindow", Recording)
    config = Config(threshold_dbfs=-10.0, min_duration_s=0.1, debounce_s=0.1, tagging=True)
    events = list(service.run_pipeline(_quiet_source(frames), config))
    assert events == [], "the quiet source must not produce events, or this measures nothing"
    return seen[0]


def test_the_feature_buffer_stays_bounded_through_a_quiet_stretch(monkeypatch):
    """The gate. 2000 frames with no event; the buffer must not grow with the count."""
    peak = _peak_buffer_len(monkeypatch, FeatureWindow)
    assert peak <= 2, (
        f"the tagging feature buffer reached {peak} entries over {QUIET_FRAMES} quiet "
        "frames. It is pruned against the detector's open-event start, and no event "
        "opens here, so it must never hold more than the frame in hand."
    )


def test_that_gate_goes_red_against_the_pruning_rule_it_replaced(monkeypatch):
    """Canary: the pre-#63 rule, measured by the same gate, grows with the frame count.

    `prune` is neutered to a no-op, which is exactly what the old code did on this
    input -- the only prune sat inside `if event is not None:` and no event ever closed.
    A gate that cannot show the defect it was written for is not a gate.
    """

    class PreIssue63(FeatureWindow):
        def prune(self, active_since: float | None) -> None:
            return  # the old behaviour on a quiet stretch: never pruned

    peak = _peak_buffer_len(monkeypatch, PreIssue63)
    assert peak == QUIET_FRAMES, f"expected unbounded growth to {QUIET_FRAMES}, saw {peak}"


def test_the_buffer_holds_one_event_and_then_empties():
    """The other half of "bounded": it must still retain what tagging needs, and let go.

    A long event legitimately holds its own frames -- that is the documented ceiling,
    one event's worth -- but nothing before its start, and nothing at all once it
    closes.
    """
    window = FeatureWindow()
    detector = Detector(threshold_dbfs=-35.0, min_duration_s=0.2, debounce_s=0.3)
    loud, quiet = [0.3, -0.3] * 5, [0.0] * 10

    lengths_during_event = []
    for i in range(40):  # 4.0 s of continuous loud
        t = i * 0.1
        window.append(t, zero_crossing_rate(loud))
        detector.push(t, dbfs(loud))
        window.prune(detector.active_since)
        lengths_during_event.append(len(window))

    # Every frame of the open event is retained: that is what mean_over needs.
    assert lengths_during_event[-1] == 40
    assert detector.active_since == 0.0

    # Close it, then feed quiet frames. The buffer must fall to empty and stay there.
    closed = None
    for i in range(40, 60):
        t = i * 0.1
        window.append(t, zero_crossing_rate(quiet))
        closed = detector.push(t, dbfs(quiet)) or closed
        window.prune(detector.active_since)
    assert closed is not None, "the event must close, or this proves nothing"
    assert len(window) == 0


def test_prune_drops_only_what_predates_the_open_event():
    window = FeatureWindow()
    for i in range(10):
        window.append(float(i), 0.5)
    window.prune(active_since=4.0)
    assert len(window) == 6  # t = 4..9 inclusive
    window.prune(active_since=None)
    assert len(window) == 0


def test_mean_over_an_empty_window_is_none_not_zero():
    """None means "no feature covers this event"; 0.0 means "measured, and silent".

    Collapsing them would tag an event the buffer knows nothing about as `ambient`,
    since classify(0.0) is AMBIENT -- an absence rendered as a value.
    """
    window = FeatureWindow()
    assert window.mean_over(0.0, 1.0) is None
    window.append(0.5, 0.0)
    assert window.mean_over(0.0, 1.0) == 0.0


def test_a_tag_survives_a_long_quiet_stretch_before_the_event():
    """The fix must not have bought its bound by dropping what tagging reads.

    Same event as test_pipeline_tags_bark_like, preceded by 500 quiet frames -- the
    stretch that used to fill the buffer. The tag must be identical.
    """
    config = Config(threshold_dbfs=-35.0, min_duration_s=0.2, debounce_s=0.3, tagging=True)
    loud = _loud(alternating=True)
    frames: list[tuple[float, list[float]]] = [(i * 0.1, [0.0] * 10) for i in range(500)]
    base = 50.0
    frames += [(base + i * 0.1, loud) for i in range(6)]
    frames.append((base + 1.0, [0.0] * 10))  # gap > debounce closes the event
    events = list(run_pipeline(_source(frames), config))
    assert len(events) == 1
    assert events[0].coarse_tag == BARK_LIKE
