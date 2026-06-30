"""Frame-coverage accounting and the atomic heartbeat writer."""

from __future__ import annotations

import json

from monitor.health import CaptureStats, write_health


def test_coverage_is_one_when_nothing_dropped():
    assert CaptureStats().coverage == 1.0
    assert CaptureStats(frames_seen=100, frames_dropped=0).coverage == 1.0


def test_coverage_reflects_drops():
    assert CaptureStats(frames_seen=90, frames_dropped=10).coverage == 0.9


def test_write_health_is_atomic_and_valid_json(tmp_path):
    path = tmp_path / "health.json"
    write_health(path, {"status": "ok", "frames_seen": 5})
    assert json.loads(path.read_text()) == {"status": "ok", "frames_seen": 5}
    # No leftover temp file from the atomic replace.
    assert not (tmp_path / "health.json.tmp").exists()


def test_write_health_overwrites(tmp_path):
    path = tmp_path / "health.json"
    write_health(path, {"n": 1})
    write_health(path, {"n": 2})
    assert json.loads(path.read_text())["n"] == 2
