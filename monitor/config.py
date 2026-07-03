"""Runtime configuration: detection knobs, calibration, quiet hours, db path.

Loaded from a small JSON file (stdlib only — tomllib is 3.11+ and we target 3.9).
Every field has a documented default so the monitor runs with no config at all, and
every field is validated on construction so a bad config fails loudly, not silently.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta, timezone, tzinfo
from pathlib import Path

try:  # zoneinfo is stdlib from 3.9; tzdata may be absent on some hosts.
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - zoneinfo always present on 3.9+
    ZoneInfo = None  # type: ignore[assignment,misc]

    class ZoneInfoNotFoundError(Exception):  # type: ignore[no-redef]
        pass


class ConfigError(ValueError):
    """Raised when a configuration value is invalid."""


@dataclass(frozen=True)
class QuietHours:
    """A daily quiet-hours window, local time, e.g. 22:00 -> 08:00 (wraps midnight)."""

    start_hour: int = 22
    end_hour: int = 8

    def __post_init__(self) -> None:
        for h in (self.start_hour, self.end_hour):
            if not 0 <= h <= 24:
                raise ConfigError(f"quiet hour out of range: {h}")

    def contains(self, dt: datetime) -> bool:
        """True if the local time of dt falls within the quiet-hours window."""
        t = dt.time()
        start = time(hour=self.start_hour % 24)
        end = time(hour=self.end_hour % 24)
        if start <= end:
            return start <= t < end
        # Wraps midnight (e.g. 22:00 -> 08:00).
        return t >= start or t < end

    def overlap_seconds(self, start_dt: datetime, end_dt: datetime) -> float:
        """Seconds of the half-open interval [start_dt, end_dt) inside the quiet window.

        Where ``contains`` classifies a single instant (used for event *counts*, which
        cannot be fractional), this pro-rates an event's *duration* across the quiet-hours
        boundary: an event that begins before 22:00 and ends after it contributes only the
        portion that actually falls inside quiet hours.

        The window is reconstructed concretely, day by day, in the local zone of the input
        datetimes so hour/day boundaries and DST are handled by real datetime arithmetic
        rather than wall-clock comparisons. We build each day's quiet interval(s) — a single
        ``[start, end)`` span for a non-wrapping window, or ``[start, 24h) + [0, end)`` for a
        window that wraps midnight — intersect each with ``[start_dt, end_dt]``, and sum.
        Adding whole hours onto local midnight keeps ``end_hour == 24`` exact and is
        fold-agnostic (deterministic across a DST transition, if imprecise by an hour at the
        exact fold — acceptable and documented).
        """
        if end_dt <= start_dt:
            return 0.0
        tz = start_dt.tzinfo
        s = self.start_hour % 24
        e = self.end_hour % 24
        # A non-wrapping window is a single [s, e) slice per day; one that wraps midnight
        # splits into a late-evening [s, 24h) and an early-morning [0, e) slice.
        day_intervals = [(s, e)] if s <= e else [(s, 24), (0, e)]
        total = 0.0
        # Start a day early so a wrap window's late-evening slice from the prior date is
        # considered; iterate through end_dt's date inclusive.
        day = start_dt.date() - timedelta(days=1)
        last_day = end_dt.date()
        while day <= last_day:
            midnight = datetime.combine(day, time(0), tzinfo=tz)
            for h0, h1 in day_intervals:
                lo = max(midnight + timedelta(hours=h0), start_dt)
                hi = min(midnight + timedelta(hours=h1), end_dt)
                if hi > lo:
                    total += (hi - lo).total_seconds()
            day += timedelta(days=1)
        return total


@dataclass(frozen=True)
class Config:
    # Audio framing (live capture). Defaults suit a Raspberry Pi USB mic.
    sample_rate: int = 16000
    frame_size: int = 1600  # 100 ms frames -> one reading every 100 ms

    # Detection.
    threshold_dbfs: float = -35.0
    min_duration_s: float = 0.4
    debounce_s: float = 1.0

    # Calibration: dB to add to relative dBFS to approximate SPL. 0.0 = uncalibrated.
    calibration_offset: float = 0.0
    calibration_note: str = "Uncalibrated: levels are relative dBFS, not absolute SPL."

    quiet_hours: QuietHours = field(default_factory=QuietHours)
    # IANA time zone (e.g. "America/Los_Angeles"). Timestamps are bucketed in this
    # zone, so daily/hourly distributions and quiet hours stay correct across DST.
    tz: str = "UTC"

    # Operations.
    db_path: str = "olive.db"
    retention_days: int = 0  # 0 = keep everything; >0 prunes events older than N days
    health_path: str = ""  # where the monitor writes its heartbeat JSON ("" = disabled)
    tagging: bool = False  # compute a coarse bark-like/ambient hint per event (no audio)

    # Device/site metadata for data lineage and the bias audit.
    device_label: str = "olive-monitor"
    mic_model: str = ""
    placement_note: str = ""

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ConfigError("sample_rate must be positive")
        if self.frame_size <= 0:
            raise ConfigError("frame_size must be positive")
        if self.min_duration_s < 0 or self.debounce_s < 0:
            raise ConfigError("min_duration_s and debounce_s must be non-negative")
        if not -200.0 <= self.threshold_dbfs <= 0.0:
            raise ConfigError("threshold_dbfs must be within [-200, 0] dBFS")
        if self.retention_days < 0:
            raise ConfigError("retention_days must be non-negative")

    def tzinfo(self) -> tzinfo:
        """Resolve the configured zone, falling back to UTC if tzdata is unavailable."""
        if ZoneInfo is None:
            return timezone.utc
        try:
            return ZoneInfo(self.tz)
        except (ZoneInfoNotFoundError, ValueError):
            return timezone.utc

    @classmethod
    def load(cls, path: Path | None) -> Config:
        """Load config from JSON, falling back to defaults for any missing field."""
        if path is None or not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        qh = data.pop("quiet_hours", None)
        kwargs = dict(data)
        if qh is not None:
            kwargs["quiet_hours"] = QuietHours(**qh)
        try:
            return cls(**kwargs)
        except TypeError as exc:  # unknown key in the JSON
            raise ConfigError(f"invalid config in {path}: {exc}") from exc

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
