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
from collections.abc import Callable, Iterable, Iterator
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

    Levels are computed and stored as **raw** dBFS — no calibration offset is baked in,
    so a later recalibration never changes the meaning of a stored row. `threshold_dbfs`
    is therefore defined against raw dBFS as well. The calibration offset is an append-
    only history in the store and is applied at *render* time (see report/render.py).
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
        # Store the raw dBFS level; the calibration offset is applied at render time so
        # the threshold and every persisted row are defined against the same raw scale.
        level = dbfs(frame)
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


def checkpointed(
    source: Iterable[tuple[float, list[float]]],
    interval_s: float,
    checkpoint: Callable[[], None],
    *,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[tuple[float, list[float]]]:
    """Pass frames straight through, invoking ``checkpoint`` on a wall-clock cadence.

    The heartbeat and session frame counters were previously written only on events
    and in the finally block, so a silent night or a power cut lost ops/coverage data.
    This wrapper piggybacks a periodic write on frame arrival (~10 Hz): once at least
    ``interval_s`` seconds of elapsed clock time have passed, the next frame triggers a
    checkpoint. No timer thread and no sockets — the heartbeat stays a file (see
    write_health), so the egress gate (tests/test_no_egress.py) keeps passing. ``clock``
    is injectable so tests can drive the cadence with a fake monotonic clock, and frames
    are never inspected or retained here, preserving the no-audio guarantee.
    """
    last = clock()
    for item in source:
        yield item
        if clock() - last >= interval_s:
            checkpoint()
            last = clock()


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
    last_level: float | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
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
    if last_level is not None:
        payload["last_level_dbfs"] = round(last_level, 1)
    return payload


def _write_status_page(config: Config, store: EventStore, payload: dict[str, object]) -> None:
    """Render the static local status page next to the heartbeat, best-effort.

    Guarded so a rendering failure never kills the monitor loop — a broken status page
    must not take down capture. Lazily imports report.status to avoid a hard monitor->
    report dependency at module load and any import cycle.
    """
    status_path = config.status_html_path()
    if not status_path:
        return
    try:
        from report.status import collect_status_aggregates, render_status, write_status

        updated_at = payload.get("updated_at")
        now = float(updated_at) if isinstance(updated_at, (int, float)) else time.time()
        aggregates = collect_status_aggregates(store, config, now=now)
        html = render_status(
            payload,
            aggregates,
            now=now,
            heartbeat_interval_s=config.checkpoint_interval_s,
        )
        write_status(status_path, html)
    except Exception as exc:
        print(f"status page not written ({exc}).")


def _bootstrap_session(store: EventStore, config: Config, started_at: float) -> int:
    """Prune per retention policy and open this run's session-lineage record.

    Calibration is a single source of truth owned by `olive-calibrate`. The monitor
    never writes it; it only reads the offset in force for this session's lineage
    record, falling back to the config's bootstrap value if no calibration exists yet.
    """
    stored_calibration = store.get_calibration()
    calibration_offset, calibration_note = (
        stored_calibration
        if stored_calibration is not None
        else (config.calibration_offset, config.calibration_note)
    )
    if config.retention_days > 0:
        removed = store.prune(before=started_at - config.retention_days * 86400)
        if removed:
            print(f"Retention: pruned {removed} event(s) older than {config.retention_days} days.")
    return store.start_session(
        started_at=started_at,
        device_label=config.device_label,
        mic_model=config.mic_model,
        placement_note=config.placement_note,
        tz=config.tz,
        calibration_offset=calibration_offset,
        calibration_note=calibration_note,
        app_version=__version__,
        threshold_dbfs=config.threshold_dbfs,
        min_duration_s=config.min_duration_s,
        debounce_s=config.debounce_s,
        sample_rate=config.sample_rate,
        frame_size=config.frame_size,
    )


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
    session_id = _bootstrap_session(store, config, started_at)
    stats = CaptureStats()
    # Clock-integrity guard: watch for wall-vs-monotonic divergence (RTC-less Pi hazard).
    guard = ClockGuard(tolerance_s=config.clock_jump_tolerance_s)
    anomaly_count = 0

    from monitor.capture_live import live_source  # lazy: optional audio dependency

    def make_source() -> Iterator[tuple[float, list[float]]]:
        return live_source(
            sample_rate=config.sample_rate, frame_size=config.frame_size, stats=stats
        )

    latest_level: float | None = None

    def heartbeat() -> None:
        payload = _health_payload(
            config,
            stats,
            started_at=started_at,
            now=now or time.time(),
            session_id=session_id,
            clock_anomalies=anomaly_count,
            last_level=latest_level,
        )
        if config.health_path:
            write_health(config.health_path, payload)
        _write_status_page(config, store, payload)

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

    def checkpoint() -> None:
        # Time-driven flush: refresh the heartbeat and persist the running frame
        # counters so a silent night or a power cut can't lose ops/coverage data.
        # ended_at is left unset (None) so a checkpoint never marks the session ended;
        # only the finally block records the real end time. The clock guard rides the
        # same cadence so anomalies are caught on quiet nights too, not only on events.
        check_clock()
        heartbeat()
        store.update_session(
            session_id,
            frames_seen=stats.frames_seen,
            frames_dropped=stats.frames_dropped,
        )

    print(
        f"Monitoring (threshold {config.threshold_dbfs} dBFS). "
        f"Logging events to {config.db_path}. Audio is never recorded. Ctrl-C to stop."
    )

    def record_gap(start: float, end: float, reason: str) -> None:
        # Persist an outage span so "no data" is later reported distinctly from quiet.
        store.add_gap(start, end, reason, session_id=session_id)

    heartbeat()
    try:
        for event in run_pipeline(
            checkpointed(
                resilient_source(make_source, on_gap=record_gap),
                config.checkpoint_interval_s,
                checkpoint,
            ),
            config,
            store,
            stats=stats,
            session_id=session_id,
        ):
            latest_level = event.peak_level
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
