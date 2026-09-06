"""Threshold sensitivity (EXP-03): would this pattern survive a different threshold?

The strongest attack on a level-only record is "you picked the threshold that flatters
you". This answers it before it is asked, from data already stored, offline and
deterministically -- and it answers it *honestly*, which for this question means being
explicit about which of the two directions the stored data can actually speak to.

What is stored, and what each part can support
----------------------------------------------

Two records survive the minute they describe. Raw samples do not (that is the privacy
design, not an oversight), so nothing here re-runs the detector.

* **Per-event peaks.** An event was detected because its level crossed the configured
  threshold `T`. Its `peak_level` says how far past `T` it went, so for any
  `T' >= T` the events whose peak still clears `T'` are exactly derivable.
* **Per-minute maxima** from the ambient ledger (EXP-01). Every monitored minute carries
  the loudest level seen in it, whether or not anything crossed `T`. So for any `T'`,
  above or below `T`, the minutes containing a level at or above `T'` are exactly
  derivable.

The asymmetry that the table must not hide
------------------------------------------

Raising the threshold is answerable from event peaks. **Lowering it is not**: an event
that never crossed `T` was never written down, so no count of stored events can say how
many events a lower threshold would have produced. The number that *is* derivable at a
lower threshold -- the count of events already recorded, every one of which clears any
`T' <= T` -- happens to equal the headline count exactly, always, on every log. Printing
it in the event-count column would render "we cannot know" as a stable number, and a
stable number in a sensitivity table reads as "the result is insensitive here". That is
this repository's dominant defect class (see `tests/test_absence_as_value.py`), in the
one place built to argue that the record is honest.

So the event-count column is `None` below the configured threshold, rendered as a floor
("at least N; events under the configured threshold were never recorded") rather than as
a measurement, and the loud-minutes column -- which the ledger *can* answer in both
directions -- carries the signal there.

Approximate, and said so
------------------------

Even above `T`, re-detection from stored aggregates is not the detector:

* A higher threshold can split one event into several or shorten it, so
  `events_at_or_above` counts *events that still cross*, not events the detector would
  emit. It is an upper bound on how many distinct events survive.
* A minute is not an event: one minute can hold several, and one event can span many.

Both are stated in `SENSITIVITY_APPROXIMATION_NOTE`, which the renderer prints beside the
table and `tests/test_sensitivity.py` pins. **The headline counts never move.** Nothing in
this module feeds `Summary`; it is read-only over the same inputs.
"""

from __future__ import annotations

from dataclasses import dataclass

from monitor.ambient import MinuteLevel
from monitor.detector import Event

# The deltas the table reports, in dB, relative to the configured threshold. Symmetric and
# fixed rather than configurable: the point is a standard, comparable exhibit, and a reader
# choosing the offsets would be choosing the answer.
SENSITIVITY_DELTAS_DB: tuple[float, ...] = (-6.0, -3.0, 0.0, 3.0, 6.0)

SENSITIVITY_APPROXIMATION_NOTE = (
    "Re-detection from minute-level aggregates is approximate; the headline counts are the "
    "measured ones and do not change. A higher threshold can split or shorten an event, so "
    "the event column counts events whose peak still clears the threshold, not events the "
    "detector would emit. A minute is not an event: one minute can contain several, and one "
    "event can span many."
)

SENSITIVITY_FLOOR_NOTE = (
    "Below the configured threshold the event column is a floor, not a count. An event that "
    "never crossed the configured threshold was never recorded, so no stored data can say "
    "how many a lower threshold would have found."
)

SENSITIVITY_SCALE_NOTE = (
    "Thresholds here are on the raw dBFS scale the detector compares against -- the same "
    "scale as the configured threshold under Methodology. Calibration offsets are applied "
    "when the report is rendered and never change what was detected, so a sensitivity "
    "recount has to be done on the scale detection actually used."
)

SENSITIVITY_UNAVAILABLE_NOTE = (
    "Sensitivity analysis unavailable: the ambient ledger is not enabled, so this record "
    "holds no per-minute levels to recount against other thresholds. Nothing here says the "
    "pattern is insensitive to the threshold -- only that this record cannot test it."
)


@dataclass(frozen=True)
class SensitivityRow:
    """One alternative threshold, and what the stored record supports about it."""

    delta_db: float
    threshold_dbfs: float
    # Events whose recorded peak still clears `threshold_dbfs`. None below the configured
    # threshold, where the question is unanswerable from stored events -- never 0, and
    # never the headline count wearing a recomputation's clothes.
    events_at_or_above: int | None
    # Minutes of the ambient ledger whose loudest level reached `threshold_dbfs`. Derivable
    # in both directions, which is why this column carries the signal below the threshold.
    loud_minutes: int


@dataclass(frozen=True)
class Sensitivity:
    """The whole exhibit. `rows` is empty only when there is no ambient ledger."""

    configured_threshold_dbfs: float
    headline_event_count: int
    minutes_covered: int
    rows: list[SensitivityRow]

    @property
    def available(self) -> bool:
        """False when the ambient ledger holds nothing, i.e. there is nothing to recount."""
        return bool(self.rows)


def sensitivity(
    events: list[Event],
    minute_levels: list[MinuteLevel],
    *,
    threshold_dbfs: float,
    deltas_db: tuple[float, ...] = SENSITIVITY_DELTAS_DB,
) -> Sensitivity:
    """Recount the record at `threshold_dbfs + d` for each `d`, from stored aggregates.

    Pure and deterministic: same inputs, same rows, in the order of `deltas_db`.

    **Feed it raw, uncalibrated levels and the raw configured threshold.** Unlike
    `summarize` and `summarize_ambient`, which render calibrated levels for a reader, this
    is a question about *detection*, and `threshold_dbfs` is defined against the raw dBFS
    scale as stored -- calibration is applied at render time and never changed what the
    detector did (`monitor/config.py`, ADR-0003). Adjusting one side and not the other
    would compare two different scales and quietly move every row. The renderer prints
    `SENSITIVITY_SCALE_NOTE` beside the table so the reader is told which scale this is.

    With no ambient ledger the result is `available == False` and carries no rows. That is
    deliberate: an event-only table would be derivable above the threshold and blank below
    it, and a half-table invites reading the blank half as zero.
    """
    peaks = sorted(e.peak_level for e in events)
    maxima = sorted(m.max_dbfs for m in minute_levels)

    rows: list[SensitivityRow] = []
    if maxima:
        for delta in deltas_db:
            alt = threshold_dbfs + delta
            rows.append(
                SensitivityRow(
                    delta_db=delta,
                    threshold_dbfs=alt,
                    events_at_or_above=(
                        sum(1 for p in peaks if p >= alt) if delta >= 0.0 else None
                    ),
                    loud_minutes=sum(1 for m in maxima if m >= alt),
                )
            )

    return Sensitivity(
        configured_threshold_dbfs=threshold_dbfs,
        headline_event_count=len(events),
        minutes_covered=len(minute_levels),
        rows=rows,
    )
