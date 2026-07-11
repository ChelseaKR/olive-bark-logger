"""Time-driven heartbeat and crash-safe session counters (FIX-04).

The heartbeat and the session frame counters used to be written only when an event
fired and once more in the finally block. A silent night (no events) or a power cut
(no finally) therefore lost ops/coverage data. `checkpointed` flushes both on a
wall-clock cadence, piggybacking on frame arrival with no threads and no sockets.

These tests drive the cadence with a fake monotonic clock and a synthetic silent
source whose simulated wall time spans two hours, and prove that counters land on
disk mid-run even when the process never reaches its finally block.
"""

from __future__ import annotations

import json

import pytest
from monitor.config import Config, ConfigError
from monitor.health import CaptureStats, write_health
from monitor.service import checkpointed, run_pipeline
from store import EventStore

# One simulated wall-second of clock time per frame, so cadence math is exact:
# a 30 s interval fires every 30 frames, and a two-hour night is 7200 frames.
NIGHT_FRAMES = 7200
INTERVAL_S = 30.0


class FakeClock:
    """A monotonic clock the test advances by hand (via the source below)."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t


def _silent_night(clock: FakeClock, n: int) -> object:
    """Yield n quiet (t, frame) pairs, advancing the fake clock one second per frame.

    The frame is two silent samples: dbfs floors it well below any threshold, so the
    detector emits no events — exactly the silent-night case that used to starve the
    heartbeat of updates.
    """
    for i in range(1, n + 1):
        clock.t = float(i)
        yield (i * 0.1, [0.0, 0.0])


def _start_session(store: EventStore) -> int:
    return store.start_session(
        started_at=1000.0,
        device_label="pi-test",
        mic_model="",
        placement_note="",
        tz="UTC",
        calibration_offset=0.0,
        calibration_note="",
        app_version="test",
    )


def test_config_exposes_checkpoint_interval_default_and_json_override(tmp_path):
    assert Config().checkpoint_interval_s == 30.0
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"checkpoint_interval_s": 5.0}))
    assert Config.load(p).checkpoint_interval_s == 5.0
    with pytest.raises(ConfigError):
        Config(checkpoint_interval_s=0.0)


def test_checkpointed_fires_on_wall_clock_cadence():
    clock = FakeClock()
    fires: list[float] = []
    gen = checkpointed(
        _silent_night(clock, NIGHT_FRAMES),
        INTERVAL_S,
        lambda: fires.append(clock.t),
        clock=clock,
    )
    for _ in gen:
        pass
    # Two hours of wall time, a checkpoint every 30 s -> 240 checkpoints, on the dot,
    # even though not one audio event occurred.
    assert fires == [float(s) for s in range(30, NIGHT_FRAMES + 1, 30)]
    assert len(fires) == 240


def test_checkpointed_does_not_fire_before_interval_elapses():
    clock = FakeClock()
    fires: list[float] = []
    # 29 frames -> 29 simulated seconds, just short of the 30 s interval.
    gen = checkpointed(
        _silent_night(clock, 29),
        INTERVAL_S,
        lambda: fires.append(clock.t),
        clock=clock,
    )
    for _ in gen:
        pass
    assert fires == []


def test_checkpoint_persists_frame_counters_across_crash(tmp_path):
    db = tmp_path / "olive.db"
    store = EventStore(db)
    sid = _start_session(store)
    stats = CaptureStats()
    clock = FakeClock()

    def checkpoint() -> None:
        # Mirrors service.main's checkpoint: flush counters without an ended_at, so a
        # periodic write never marks the session ended.
        store.update_session(
            sid, frames_seen=stats.frames_seen, frames_dropped=stats.frames_dropped
        )

    gen = checkpointed(_silent_night(clock, 600), INTERVAL_S, checkpoint, clock=clock)

    # Consume only part of the stream, then abandon it: a power cut before the finally
    # block ever runs. update_session is never called with an ended_at.
    for i, _frame in enumerate(gen, start=1):
        stats.frames_seen += 1
        if i == 100:
            break

    # Reopen the database on a fresh connection (the crashed process never closed its
    # own) and confirm the last mid-run checkpoint survived. Checkpoints fired at
    # frames 30/60/90 reading frames_seen 30/60/90; frame 100 never triggered one.
    with EventStore(db) as reopened:
        s = reopened.latest_session()
        assert s is not None
        assert s.frames_seen == 90
        assert s.ended_at is None  # a crash, not a graceful shutdown
    store.close()


def test_run_pipeline_checkpointing_keeps_health_fresh(tmp_path):
    db = tmp_path / "olive.db"
    health = tmp_path / "olive-health.json"
    config = Config(db_path=str(db), health_path=str(health), checkpoint_interval_s=INTERVAL_S)
    store = EventStore(db)
    sid = _start_session(store)
    stats = CaptureStats()
    clock = FakeClock()
    fires: list[float] = []

    def checkpoint() -> None:
        write_health(
            health,
            {"status": "ok", "updated_at": clock.t, "frames_seen": stats.frames_seen},
        )
        store.update_session(
            sid, frames_seen=stats.frames_seen, frames_dropped=stats.frames_dropped
        )
        fires.append(clock.t)

    source = checkpointed(
        _silent_night(clock, NIGHT_FRAMES), config.checkpoint_interval_s, checkpoint, clock=clock
    )
    events = list(run_pipeline(source, config, store, stats=stats, session_id=sid))

    assert events == []  # silent night: no events at all
    assert len(fires) == 240  # yet the heartbeat kept beating on the clock cadence
    payload = json.loads(health.read_text(encoding="utf-8"))
    assert payload["updated_at"] == float(NIGHT_FRAMES)  # fresh right to the end
    assert payload["frames_seen"] == NIGHT_FRAMES
    # And the coverage counters are on disk mid-run, not only in the finally block.
    persisted = store.latest_session()
    assert persisted is not None
    assert persisted.frames_seen == NIGHT_FRAMES
    assert persisted.ended_at is None
    store.close()
