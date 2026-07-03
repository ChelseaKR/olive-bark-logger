"""Runtime configuration: detection knobs, calibration, quiet hours, db path.

Loaded from a small JSON file (stdlib only — tomllib is 3.11+ and we target 3.9).
Every field has a documented default so the monitor runs with no config at all, and
every field is validated on construction so a bad config fails loudly, not silently.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone, tzinfo
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
    # Clock-integrity guard: flag a wall-vs-monotonic divergence larger than this many
    # seconds as a clock jump (important on RTC-less Pis where NTP sync lurches the clock).
    clock_jump_tolerance_s: float = 2.0

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
        if self.clock_jump_tolerance_s <= 0:
            raise ConfigError("clock_jump_tolerance_s must be positive")

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
