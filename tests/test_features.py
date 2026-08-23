"""Coarse feature extraction and optional event tagging in the pipeline."""

from __future__ import annotations

from monitor.config import Config
from monitor.features import AMBIENT, BARK_LIKE, classify, zero_crossing_rate
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


def test_tagger_buffer_does_not_grow_during_quiet():
    """Regression test for #63: feats buffer must not accumulate frames during quiet stretches."""
    from monitor.service import _TaggerSink

    config = Config(threshold_dbfs=-35.0, min_duration_s=0.2, debounce_s=0.3, tagging=True)
    sink = _TaggerSink(config, None, None)
    for i in range(100):
        sink.push_frame(i * 0.1, [0.0] * 10, relevant=False)
    assert len(sink._feats) == 0

    # Pushing loud frames records them
    for i in range(5):
        sink.push_frame(10.0 + i * 0.1, _loud(alternating=True), relevant=True)
    assert len(sink._feats) == 5

    # A quiet frame when an event is done clears
    sink.push_frame(11.0, [0.0] * 10, relevant=False)
    assert len(sink._feats) == 0

    # End-to-end pipeline run with a long quiet stretch
    quiet_frames = [(i * 0.1, [0.0] * 10) for i in range(100)]
    loud_frames = [(10.0 + i * 0.1, _loud(alternating=True)) for i in range(6)]
    closing_quiet = [(11.0, [0.0] * 10)]
    events = list(run_pipeline(_source(quiet_frames + loud_frames + closing_quiet), config))
    assert len(events) == 1
    assert events[0].coarse_tag == BARK_LIKE
