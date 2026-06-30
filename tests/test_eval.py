"""Eval: detection accuracy against a labeled synthetic session.

A synthetic session with known loud regions stands in for the labeled recording the
roadmap calls for (deterministic, no hardware, no stored audio). We assert the monitor
recovers the right number of events and that each lines up with a labeled region.
"""

from __future__ import annotations

from monitor.capture import LoudRegion, synthetic_session
from monitor.config import Config
from monitor.service import run_pipeline

# Labeled ground truth: two distinct loud spans in an otherwise quiet 20 s session.
LABELS = [
    LoudRegion(start_s=2.0, end_s=5.0, amplitude=0.3),
    LoudRegion(start_s=10.0, end_s=13.0, amplitude=0.4),
]
SESSION_SECONDS = 20.0


def _detect(threshold=-35.0, min_duration=0.4, debounce=1.0):
    config = Config(threshold_dbfs=threshold, min_duration_s=min_duration, debounce_s=debounce)
    source = synthetic_session(
        SESSION_SECONDS, LABELS, sample_rate=config.sample_rate, frame_size=config.frame_size
    )
    return list(run_pipeline(source, config))


def test_recovers_the_labeled_event_count():
    events = _detect()
    assert len(events) == len(LABELS)


def test_detected_events_align_with_labels():
    events = sorted(_detect(), key=lambda e: e.start)
    for ev, label in zip(events, LABELS):
        # Detection should start within one frame of the label and not overrun it much.
        assert abs(ev.start - label.start_s) <= 0.2, (ev.start, label.start_s)
        assert abs(ev.end - label.end_s) <= 0.2, (ev.end, label.end_s)
        assert ev.peak_level >= -35.0


def test_no_false_positives_in_quiet_session():
    quiet = list(
        run_pipeline(
            synthetic_session(SESSION_SECONDS, [], sample_rate=16000, frame_size=1600),
            Config(),
        )
    )
    assert quiet == []


def test_threshold_too_high_detects_nothing():
    # If the threshold is above the loud level, no events should be reported.
    assert _detect(threshold=0.0) == []
