"""Advisory drift watch: has the ambient baseline moved since calibration? (EXP-04)

A microphone that gets nudged, or an enclosure that fills with dust over a winter,
changes what "loud" means without changing a single configured number. Nobody notices,
because every screen keeps reporting the same threshold in the same units. Weeks of
counts then mean something different from the weeks before them, and nothing in the
record says so.

This module compares two ambient baselines drawn from the opt-in minute ledger
(``monitor/ambient.py``, EXP-01): a *reference* window taken right after the current
calibration epoch began, and a *recent* window at the end of the record. When the
median or L90 has moved further than a tolerance, the check returns an advisory.

It is advisory on purpose. Detection parameters are frozen per session for provenance
(FIX-02, ADR 0019), so a tool that quietly re-tuned itself would make two nights
incomparable and destroy the thing the evidence is for. The decision, and the adaptive
alternative that was rejected, are recorded in
``docs/adr/0030-advisory-drift-watch-never-adaptive-detection.md``.

The comparison itself is pure: :func:`summarize_baseline` and :func:`compare_baselines`
take minute rows and return a verdict. :func:`evaluate` is the thin shell that reads the
two windows out of the store and calls them, so the service has no arithmetic in it. No
clock is read here, no audio is touched, and nothing leaves the machine.

The one rule that shapes the whole design: **a check that could not run is not a check
that found nothing.** A disabled ledger, a window with no minutes in it, or a store with
no calibration epoch each produce :data:`UNAVAILABLE` with a stated reason, never
"steady". Reporting "no drift" for a comparison that never happened would be the same
defect this repository has already removed from frame coverage, quiet-hours coverage and
the gap ledger: an absence rendered as a reassuring value.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Protocol

from monitor.ambient import MinuteLevel, percentile

#: The percentile rank of L90 in the ascending-sorted level distribution. Same
#: convention as :mod:`monitor.ambient`, restated here so the two cannot drift apart
#: silently; ``tests/test_drift.py`` asserts they are equal.
L90_PERCENTILE_RANK = 10.0

#: Status values. Deliberately three, not two: "the baseline has not moved" and "the
#: baseline could not be compared" are different facts and every surface must be able
#: to tell a reader which one it has.
STEADY = "steady"
ADVISORY = "advisory"
UNAVAILABLE = "unavailable"

#: Reasons a comparison could not be made. Each is a complete sentence fragment a
#: report can print after "drift watch unavailable: ".
REASON_LEDGER_DISABLED = "ambient ledger not enabled"
REASON_NO_CALIBRATION = "no calibration epoch has been recorded"
REASON_NO_REFERENCE = "no ambient minutes were recorded just after the calibration epoch"
REASON_NO_RECENT = "no ambient minutes were recorded in the recent window"
REASON_WINDOWS_OVERLAP = (
    "the calibration epoch is more recent than one comparison window, so the reference "
    "and recent windows overlap"
)


@dataclass(frozen=True)
class AmbientBaseline:
    """Median and L90 of one window of ambient minutes. Two numbers and a count."""

    minute_count: int
    median_dbfs: float
    l90_dbfs: float


@dataclass(frozen=True)
class DriftAdvisory:
    """One recorded observation that the ambient baseline has moved. Numbers only."""

    calibration_epoch: float  # effective_from of the epoch the reference window follows
    reference_start: float
    reference_end: float
    recent_start: float
    recent_end: float
    reference_minutes: int
    recent_minutes: int
    median_delta_db: float  # recent - reference; positive means the room got louder
    l90_delta_db: float
    tolerance_db: float

    @property
    def largest_delta_db(self) -> float:
        """The signed delta that tripped the tolerance (the larger in magnitude)."""

        return (
            self.median_delta_db
            if abs(self.median_delta_db) >= abs(self.l90_delta_db)
            else self.l90_delta_db
        )


@dataclass(frozen=True)
class DriftCheck:
    """The outcome of one comparison: a status, and either a reason or an advisory.

    Exactly one of ``reason`` and ``advisory`` is set for the ``unavailable`` and
    ``advisory`` statuses respectively; ``steady`` carries the measured baselines so a
    reader can see the comparison that was actually made rather than taking "steady" on
    trust.
    """

    status: str
    reason: str | None = None
    advisory: DriftAdvisory | None = None
    reference: AmbientBaseline | None = None
    recent: AmbientBaseline | None = None

    @property
    def ran(self) -> bool:
        """Did a real comparison happen? False for :data:`UNAVAILABLE`."""

        return self.status != UNAVAILABLE


def summarize_baseline(minutes: list[MinuteLevel]) -> AmbientBaseline | None:
    """Median and L90 across a window's per-minute summaries, or ``None`` if empty.

    ``None``, not a zero-filled baseline: a window with no minutes in it has no
    baseline, and returning numbers for it would let a comparison against nothing
    report a delta of 0 dB and read as "steady".

    The day-level rollup in ``report/aggregate.py`` takes the same approximation, and
    for the same reason: raw samples no longer exist past the minute that summarized
    them, so a window statistic is computed across the per-minute statistics rather
    than across readings.
    """

    if not minutes:
        return None
    medians = sorted(m.median_dbfs for m in minutes)
    l90s = sorted(m.l90_dbfs for m in minutes)
    return AmbientBaseline(
        minute_count=len(minutes),
        median_dbfs=statistics.median(medians),
        l90_dbfs=percentile(l90s, L90_PERCENTILE_RANK),
    )


def compare_baselines(
    reference: AmbientBaseline | None,
    recent: AmbientBaseline | None,
    *,
    calibration_epoch: float | None,
    reference_window: tuple[float, float],
    recent_window: tuple[float, float],
    tolerance_db: float,
    ledger_enabled: bool = True,
) -> DriftCheck:
    """Compare two ambient baselines and decide whether to raise an advisory.

    Every path that cannot compare returns :data:`UNAVAILABLE` with the reason, in the
    order a reader would ask them: was the ledger even on, is there a calibration epoch
    to measure from, was anything recorded just after it, was anything recorded lately.
    """

    if not ledger_enabled:
        return DriftCheck(status=UNAVAILABLE, reason=REASON_LEDGER_DISABLED)
    if calibration_epoch is None:
        return DriftCheck(status=UNAVAILABLE, reason=REASON_NO_CALIBRATION)
    if reference is None:
        return DriftCheck(status=UNAVAILABLE, reason=REASON_NO_REFERENCE)
    if recent is None:
        return DriftCheck(status=UNAVAILABLE, reason=REASON_NO_RECENT, reference=reference)

    median_delta = recent.median_dbfs - reference.median_dbfs
    l90_delta = recent.l90_dbfs - reference.l90_dbfs
    if max(abs(median_delta), abs(l90_delta)) <= tolerance_db:
        return DriftCheck(status=STEADY, reference=reference, recent=recent)
    return DriftCheck(
        status=ADVISORY,
        reference=reference,
        recent=recent,
        advisory=DriftAdvisory(
            calibration_epoch=calibration_epoch,
            reference_start=reference_window[0],
            reference_end=reference_window[1],
            recent_start=recent_window[0],
            recent_end=recent_window[1],
            reference_minutes=reference.minute_count,
            recent_minutes=recent.minute_count,
            median_delta_db=median_delta,
            l90_delta_db=l90_delta,
            tolerance_db=tolerance_db,
        ),
    )


class AmbientMinuteSource(Protocol):
    """The slice of :class:`store.EventStore` this watch reads. Read-only."""

    def minute_levels(
        self, *, since: float | None = ..., until: float | None = ...
    ) -> list[MinuteLevel]: ...


def evaluate(
    source: AmbientMinuteSource,
    *,
    calibration_epoch: float | None,
    now: float,
    window_hours: float,
    tolerance_db: float,
    ledger_enabled: bool,
) -> DriftCheck:
    """Read both windows from the minute ledger and compare them.

    The reference window is ``[epoch, epoch + window_hours)``: the room as it sounded
    immediately after the operator last calibrated, which is the moment the current
    offset was chosen to describe. The recent window is ``[now - window_hours, now)``.

    When the two windows overlap -- a calibration done less than ``window_hours`` ago --
    the comparison would be partly against itself, so it is refused rather than run: the
    result would be a small delta whatever the microphone had done, which is exactly the
    kind of number that reads as reassurance without being evidence.
    """

    if not ledger_enabled:
        return DriftCheck(status=UNAVAILABLE, reason=REASON_LEDGER_DISABLED)
    if calibration_epoch is None:
        return DriftCheck(status=UNAVAILABLE, reason=REASON_NO_CALIBRATION)

    span = window_hours * 3600.0
    reference_window = (calibration_epoch, calibration_epoch + span)
    recent_window = (now - span, now)
    if recent_window[0] < reference_window[1]:
        return DriftCheck(status=UNAVAILABLE, reason=REASON_WINDOWS_OVERLAP)

    reference = summarize_baseline(
        source.minute_levels(since=reference_window[0], until=reference_window[1])
    )
    recent = summarize_baseline(
        source.minute_levels(since=recent_window[0], until=recent_window[1])
    )
    return compare_baselines(
        reference,
        recent,
        calibration_epoch=calibration_epoch,
        reference_window=reference_window,
        recent_window=recent_window,
        tolerance_db=tolerance_db,
        ledger_enabled=True,
    )
