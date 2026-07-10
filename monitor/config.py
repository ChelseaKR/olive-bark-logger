"""Runtime configuration: detection knobs, calibration, quiet hours, db path.

Loaded from a small JSON file (stdlib only — tomllib is 3.11+ and we target 3.9).
Every field has a documented default so the monitor runs with no config at all, and
every field is validated on construction so a bad config fails loudly, not silently.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, tzinfo
from pathlib import Path

logger = logging.getLogger(__name__)

try:  # zoneinfo is stdlib from 3.9; tzdata may be absent on some hosts.
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - zoneinfo always present on 3.9+
    ZoneInfo = None  # type: ignore[assignment,misc]

    class ZoneInfoNotFoundError(Exception):  # type: ignore[no-redef]
        pass


class ConfigError(ValueError):
    """Raised when a configuration value is invalid."""


_DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_ALL_DAYS = frozenset(range(7))
_MINUTES_PER_DAY = 24 * 60  # 1440


def _fmt_minute(m: int) -> str:
    """Format a minute-of-day (0..1440) as HH:MM; 1440 renders as 00:00 (midnight)."""
    m %= _MINUTES_PER_DAY
    return f"{m // 60:02d}:{m % 60:02d}"


def _parse_hhmm(s: str) -> int:
    """Parse an "HH:MM" wall-clock string (00:00..23:59) into a minute-of-day."""
    parts = s.split(":") if isinstance(s, str) else []
    if len(parts) != 2:
        raise ConfigError(f"invalid HH:MM time: {s!r}")
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ConfigError(f"invalid HH:MM time: {s!r}") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ConfigError(f"time out of range: {s!r}")
    return h * 60 + m


def _fmt_days(days: frozenset[int]) -> str:
    """Render a day set compactly, e.g. {0,1,2,3,4} -> "Mon-Fri", {5,6} -> "Sat-Sun"."""
    ordered = sorted(days)
    groups: list[str] = []
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        if j > i:
            groups.append(f"{_DAY_NAMES[ordered[i]]}-{_DAY_NAMES[ordered[j]]}")
        else:
            groups.append(_DAY_NAMES[ordered[i]])
        i = j + 1
    return ",".join(groups)


@dataclass(frozen=True)
class QuietWindow:
    """One quiet-hours window: a minute-granular time span active on given weekdays.

    ``days`` uses 0=Mon .. 6=Sun and defaults to every day. ``start_minute`` and
    ``end_minute`` are minutes-of-day in [0, 1440]. If ``start_minute > end_minute`` the
    window wraps past midnight into the NEXT day; day membership is always decided by the
    weekday the window STARTS on. A Fri 23:00 -> 07:00 window (days={Fri}) therefore covers
    Saturday 03:00 only because it *started* on Friday, not because Saturday is a member.
    """

    start_minute: int
    end_minute: int
    days: frozenset[int] = _ALL_DAYS

    def __post_init__(self) -> None:
        object.__setattr__(self, "days", frozenset(self.days))
        for m in (self.start_minute, self.end_minute):
            if not 0 <= m <= _MINUTES_PER_DAY:
                raise ConfigError(f"quiet window minute out of range: {m}")
        if self.start_minute == self.end_minute:
            raise ConfigError("quiet window is empty (start_minute == end_minute)")
        if not self.days:
            raise ConfigError("quiet window has no active days")
        if any(not 0 <= d <= 6 for d in self.days):
            raise ConfigError(f"quiet window weekday out of range: {sorted(self.days)}")

    @property
    def wraps(self) -> bool:
        """True when the window crosses midnight (start later than end)."""
        return self.start_minute > self.end_minute

    def contains_local(self, weekday: int, minute: int) -> bool:
        """True if (weekday, minute-of-day) falls in this window.

        Start is inclusive, end is exclusive. For wrapping windows the early-morning tail
        belongs to the window that STARTED the previous day.
        """
        if not self.wraps:
            return weekday in self.days and self.start_minute <= minute < self.end_minute
        # Wrapping window: evening portion sits on the start day...
        if weekday in self.days and minute >= self.start_minute:
            return True
        # ...and the after-midnight portion belongs to the previous day's window.
        yesterday = (weekday - 1) % 7
        return yesterday in self.days and minute < self.end_minute

    def label(self) -> str:
        """Human label like "22:30-07:00" or, for a day subset, "22:30-07:00 (Mon-Fri)"."""
        span = f"{_fmt_minute(self.start_minute)}–{_fmt_minute(self.end_minute)}"  # noqa: RUF001 - intentional en dash
        if self.days != _ALL_DAYS:
            span += f" ({_fmt_days(self.days)})"
        return span

    def to_dict(self) -> dict[str, object]:
        return {
            "days": sorted(self.days),
            "start": _fmt_minute(self.start_minute),
            "end": _fmt_minute(self.end_minute),
        }


@dataclass(frozen=True)
class QuietSchedule:
    """An ordered set of quiet-hours windows evaluated as a union."""

    windows: tuple[QuietWindow, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "windows", tuple(self.windows))
        if not self.windows:
            raise ConfigError("quiet schedule has no windows")

    def contains(self, dt: datetime) -> bool:
        """True if the local wall-clock time of ``dt`` falls inside any quiet window."""
        weekday = dt.weekday()
        minute = dt.hour * 60 + dt.minute
        return any(w.contains_local(weekday, minute) for w in self.windows)

    def label(self) -> str:
        """Report-facing label joining every window, e.g. "22:30-07:00; 23:00-08:00"."""
        return "; ".join(w.label() for w in self.windows)

    @classmethod
    def from_legacy(cls, start_hour: int = 22, end_hour: int = 8) -> QuietSchedule:
        """Upgrade the old hour-only daily window into an equivalent QuietSchedule."""
        for h in (start_hour, end_hour):
            if not 0 <= h <= 24:
                raise ConfigError(f"quiet hour out of range: {h}")
        return cls((QuietWindow(start_minute=start_hour * 60, end_minute=end_hour * 60),))

    @classmethod
    def from_json(cls, data: dict[str, object]) -> QuietSchedule:
        """Build from JSON, accepting both the new windows form and the legacy hour form."""
        if "windows" in data:
            raw = data["windows"]
            if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
                raise ConfigError("quiet_hours.windows must be a list")
            windows: list[QuietWindow] = []
            for w in raw:
                if not isinstance(w, dict) or "start" not in w or "end" not in w:
                    raise ConfigError(f"invalid quiet window entry: {w!r}")
                days = w.get("days")
                day_set = _ALL_DAYS if days is None else frozenset(int(d) for d in days)
                windows.append(
                    QuietWindow(
                        start_minute=_parse_hhmm(w["start"]),
                        end_minute=_parse_hhmm(w["end"]),
                        days=day_set,
                    )
                )
            return cls(tuple(windows))
        # Legacy {"start_hour": .., "end_hour": ..} form.
        logger.warning(
            "quiet_hours {start_hour, end_hour} form is deprecated; "
            'use {"windows": [{"days": [...], "start": "HH:MM", "end": "HH:MM"}]}'
        )
        try:
            return cls.from_legacy(**data)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ConfigError(f"invalid quiet_hours: {exc}") from exc

    def to_dict(self) -> dict[str, object]:
        return {"windows": [w.to_dict() for w in self.windows]}


def QuietHours(start_hour: int = 22, end_hour: int = 8) -> QuietSchedule:
    """Deprecated legacy constructor kept for back-compat.

    Returns a :class:`QuietSchedule` equivalent to the old daily hour-only window (which
    wraps midnight when ``start_hour > end_hour``). New code should use ``QuietSchedule``.
    """
    return QuietSchedule.from_legacy(start_hour, end_hour)


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

    quiet_hours: QuietSchedule = field(default_factory=lambda: QuietSchedule.from_legacy(22, 8))
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
            kwargs["quiet_hours"] = QuietSchedule.from_json(qh)
        try:
            return cls(**kwargs)
        except TypeError as exc:  # unknown key in the JSON
            raise ConfigError(f"invalid config in {path}: {exc}") from exc

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        # Emit the JSON-friendly windows form (asdict would leave a frozenset behind).
        d["quiet_hours"] = self.quiet_hours.to_dict()
        return d
