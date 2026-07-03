"""Wire a frame source through level computation and detection into the event store.

run_pipeline is the heart of the monitor and is fully testable with a synthetic
source — no hardware, no audio files. The CLI (main) adds the unattended-operation
concerns: a capture session for lineage, frame-coverage accounting, a heartbeat file,
and automatic reconnect on device failure.

The data path is: frame -> dbfs(frame) -> detector.push(t, level) -> store.add_event.
The frame is a local variable that goes out of scope each iteration. It is never
written, buffered to disk, or sent anywhere.
"""

from __future__ import annotations

import argparse
import dataclasses
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

from store import EventStore

from monitor import __version__
from monitor.capture import resilient_source
from monitor.clock import ClockGuard
from monitor.config import Config
from monitor.detector import Detector, Event
from monitor.features import classify, zero_crossing_rate
from monitor.health import CaptureStats, write_health
from monitor.level import dbfs


def run_pipeline(
    source: Iterable[tuple[float, list[float]]],
    config: Config,
    store: EventStore | None = None,
    *,
    stats: CaptureStats | None = None,
    session_id: int | None = None,
) -> Iterator[Event]:
    """Process frames into events. Yields each event as it closes and stores it.

    Yielding (rather than only storing) keeps this a pure generator that tests can
    drive and assert on. If a store is given, events are persisted as a side effect;
    if stats is given, every processed frame is counted (for frame-coverage reporting).
    """
    detector = Detector(
        threshold_dbfs=config.threshold_dbfs,
        min_duration_s=config.min_duration_s,
        debounce_s=config.debounce_s,
    )
    # When tagging is on, keep (t, zcr) for recent frames so a closing event can be
    # classified over its own time window. The buffer is pruned past each event's end,
    # so it never holds more than one event's worth of frame features (numbers, no audio).
    feats: list[tuple[float, float]] = []

    def finish(ev: Event) -> Event:
        if config.tagging:
            ev = _attach_tag(ev, feats)
        if store is not None:
            store.add_event(ev, session_id=session_id)
        return ev

    for t, frame in source:
        if stats is not None:
            stats.frames_seen += 1
        level = dbfs(frame, calibration_offset=config.calibration_offset)
        if config.tagging:
            feats.append((t, zero_crossing_rate(frame)))
        # `frame` is not referenced again; it is dropped on the next iteration.
        event = detector.push(t, level)
        if event is not None:
            yield finish(event)
            feats = [f for f in feats if f[0] > event.end]
    final = detector.flush()
    if final is not None:
        yield finish(final)


def _attach_tag(event: Event, feats: list[tuple[float, float]]) -> Event:
    """Classify an event by the mean zero-crossing rate over its time window."""
    window = [z for (t, z) in feats if event.start <= t <= event.end]
    if not window:
        return event
    return dataclasses.replace(event, coarse_tag=classify(sum(window) / len(window)))


def _health_payload(
    config: Config,
    stats: CaptureStats,
    *,
    started_at: float,
    now: float,
    session_id: int,
    clock_anomalies: int = 0,
) -> dict[str, object]:
    return {
        "status": "ok",
        "session_id": session_id,
        "started_at": started_at,
        "updated_at": now,
        "uptime_s": round(now - started_at, 1),
        "frames_seen": stats.frames_seen,
        "frames_dropped": stats.frames_dropped,
        "frame_coverage": round(stats.coverage, 4),
        "clock_anomalies": clock_anomalies,
        "db_path": config.db_path,
        "version": __version__,
    }


def main(argv: list[str] | None = None, *, now: float = 0.0) -> int:
    parser = argparse.ArgumentParser(
        prog="olive-monitor",
        description="On-device noise monitor: logs sound-level events, never audio.",
    )
    parser.add_argument("--config", type=Path, default=None, help="path to JSON config")
    args = parser.parse_args(argv)

    config = Config.load(args.config)
    started_at = now or time.time()
    store = EventStore(config.db_path)
    store.set_calibration(config.calibration_offset, config.calibration_note)
    if config.retention_days > 0:
        removed = store.prune(before=started_at - config.retention_days * 86400)
        if removed:
            print(f"Retention: pruned {removed} event(s) older than {config.retention_days} days.")
    session_id = store.start_session(
        started_at=started_at,
        device_label=config.device_label,
        mic_model=config.mic_model,
        placement_note=config.placement_note,
        tz=config.tz,
        calibration_offset=config.calibration_offset,
        calibration_note=config.calibration_note,
        app_version=__version__,
    )
    stats = CaptureStats()
    # Clock-integrity guard: watch for wall-vs-monotonic divergence (RTC-less Pi hazard).
    guard = ClockGuard(tolerance_s=config.clock_jump_tolerance_s)
    anomaly_count = 0

    from monitor.capture_live import live_source  # lazy: optional audio dependency

    def make_source() -> Iterator[tuple[float, list[float]]]:
        return live_source(
            sample_rate=config.sample_rate, frame_size=config.frame_size, stats=stats
        )

    def heartbeat() -> None:
        if config.health_path:
            write_health(
                config.health_path,
                _health_payload(
                    config,
                    stats,
                    started_at=started_at,
                    now=now or time.time(),
                    session_id=session_id,
                    clock_anomalies=anomaly_count,
                ),
            )

    def check_clock() -> None:
        """Sample both clocks; persist and announce any divergence beyond tolerance."""
        nonlocal anomaly_count
        anomaly = guard.check(time.time(), time.monotonic())
        if anomaly is None:
            return
        anomaly_count += 1
        store.add_clock_anomaly(
            session_id=session_id,
            kind=anomaly.kind,
            wall_before=anomaly.wall_before,
            wall_after=anomaly.wall_after,
            delta=anomaly.delta,
            detected_at=anomaly.detected_at,
        )
        print(
            f"clock {anomaly.kind}: wall time moved {anomaly.delta:+.1f}s relative to "
            f"the monotonic clock (expected {anomaly.wall_before:.0f}, saw "
            f"{anomaly.wall_after:.0f}). Event timestamps around this point may be off."
        )

    print(
        f"Monitoring (threshold {config.threshold_dbfs} dBFS). "
        f"Logging events to {config.db_path}. Audio is never recorded. Ctrl-C to stop."
    )
    heartbeat()
    try:
        for event in run_pipeline(
            resilient_source(make_source),
            config,
            store,
            stats=stats,
            session_id=session_id,
        ):
            check_clock()
            print(
                f"event @ {event.start:.0f}  dur {event.duration:.1f}s  "
                f"peak {event.peak_level:.1f} dBFS"
            )
            heartbeat()
    except KeyboardInterrupt:  # pragma: no cover - interactive
        print("\nStopped.")
    finally:
        store.update_session(
            session_id,
            frames_seen=stats.frames_seen,
            frames_dropped=stats.frames_dropped,
            ended_at=now or time.time(),
        )
        heartbeat()
        store.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
