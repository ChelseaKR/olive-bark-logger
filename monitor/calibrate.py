"""Calibration and live-tuning helpers.

Two operator tasks this supports:

  * Tuning (`olive-tune`): show the live level so you can pick a threshold by ear, and
    print a suggested threshold from what was observed.
  * Calibration (`olive-calibrate`): measure the mean level while a reference SPL meter
    reads a known value, then store the offset so dBFS can be reported toward approximate
    SPL — with the limitation that it is still an estimate.

The math is pure and tested; the CLIs are thin wrappers over a frame source.
"""

from __future__ import annotations

import argparse
import statistics
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from store import EventStore

from monitor.config import Config
from monitor.level import SILENCE_FLOOR_DBFS, dbfs

Source = Iterable[tuple[float, list[float]]]


def compute_offset(measured_dbfs: float, reference_spl_db: float) -> float:
    """Offset (dB) to add to dBFS so it reads as the reference SPL: reference - measured."""
    return reference_spl_db - measured_dbfs


def suggest_threshold(levels: list[float], *, margin_db: float = 6.0) -> float:
    """Suggest a detection threshold: the ambient median plus a margin, rounded to 0.1."""
    if not levels:
        return SILENCE_FLOOR_DBFS + margin_db
    return round(statistics.median(levels) + margin_db, 1)


def meter_bar(
    level_dbfs: float, *, floor: float = -60.0, ceil: float = 0.0, width: int = 30
) -> str:
    """An ASCII level meter, e.g. '[######------] -22.0 dBFS'. Terminal-only, no network."""
    span = ceil - floor
    frac = 0.0 if span <= 0 else (level_dbfs - floor) / span
    frac = max(0.0, min(1.0, frac))
    filled = round(frac * width)
    return f"[{'#' * filled}{'-' * (width - filled)}] {level_dbfs:6.1f} dBFS"


def measure_levels(
    source: Source, *, calibration_offset: float = 0.0, max_frames: int | None = None
) -> list[float]:
    """Collect per-frame dBFS from a source (optionally capped), discarding frames."""
    levels: list[float] = []
    for _t, frame in source:
        levels.append(dbfs(frame, calibration_offset=calibration_offset))
        if max_frames is not None and len(levels) >= max_frames:
            break
    return levels


def main_calibrate(
    argv: list[str] | None = None,
    *,
    source_factory: Callable[[Config], Source] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="olive-calibrate",
        description="Measure the mean level and store an offset toward approximate SPL.",
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--reference-db", type=float, required=True, help="SPL (dB) shown on a reference meter now"
    )
    parser.add_argument(
        "--reference-instrument",
        type=str,
        default=None,
        help="make/model of the reference SPL meter, recorded for provenance",
    )
    parser.add_argument("--seconds", type=float, default=10.0, help="how long to measure")
    args = parser.parse_args(argv)

    config = Config.load(args.config)
    frames = max(1, int(args.seconds * config.sample_rate / config.frame_size))
    source = source_factory(config) if source_factory else _live(config)
    measured = statistics.fmean(measure_levels(source, max_frames=frames))
    offset = compute_offset(measured, args.reference_db)
    instrument = (
        f" Reference instrument: {args.reference_instrument}." if args.reference_instrument else ""
    )
    note = (
        f"Calibrated against a {args.reference_db:.1f} dB reference "
        f"(measured {measured:.1f} dBFS).{instrument} "
        f"Readings approximate SPL but remain estimates."
    )
    # olive-calibrate is the only writer of calibration: append a new epoch, never update.
    with EventStore(config.db_path) as store:
        store.add_calibration(offset, note, reference_instrument=args.reference_instrument)
    print(
        f"Measured {measured:.1f} dBFS at {args.reference_db:.1f} dB reference -> "
        f"offset {offset:+.1f} dB. Stored to {config.db_path}."
    )
    return 0


def main_tune(argv: list[str] | None = None) -> int:  # pragma: no cover - live meter
    parser = argparse.ArgumentParser(
        prog="olive-tune",
        description="Show the live sound level to help pick a threshold. Ctrl-C to finish.",
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    config = Config.load(args.config)

    levels: list[float] = []
    print("Live level (Ctrl-C to stop and see a suggested threshold):")
    try:
        for level in _iter_levels(_live(config), config):
            levels.append(level)
            print("\r" + meter_bar(level), end="", flush=True)
    except KeyboardInterrupt:
        pass
    print(f"\nSuggested threshold: {suggest_threshold(levels)} dBFS")
    return 0


def _iter_levels(source: Source, config: Config) -> Iterator[float]:  # pragma: no cover
    for _t, frame in source:
        yield dbfs(frame, calibration_offset=config.calibration_offset)


def _live(config: Config) -> Source:  # pragma: no cover - requires hardware
    from monitor.capture_live import live_source

    return live_source(sample_rate=config.sample_rate, frame_size=config.frame_size)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main_tune())
