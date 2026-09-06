# 0030. The drift watch advises; it never re-tunes detection (EXP-04)

**Status:** Accepted · **Date:** 2026-09-06

## Context
A microphone in a window for a season does not stay where it was put. It gets knocked
by a curtain, the enclosure fills with dust, the foam windscreen compacts, the USB
interface is unplugged and replaced a centimetre to the left. None of that changes a
single configured number, so every screen keeps reporting the same threshold in the
same units while the meaning of "loud" underneath it has moved. Weeks of counts then
mean something different from the weeks before them, and until now nothing in the
record said so.

The opt-in ambient ledger ([EXP-01](../ideation/03-expansions.md), schema v8) already
stores what is needed to notice: one bounded four-scalar summary per wall-clock minute.
Comparing the recent baseline against the window immediately after the operator last
calibrated is enough to say "the room's floor has moved 8 dB since you set the offset".

There are two things a tool can do with that observation.

## Decision
**Tell the operator. Never act on it.**

`monitor/drift.py` compares the two windows and, past a tolerance
(`drift_tolerance_db`, default 5 dB), returns an advisory. The advisory is written to a
`drift_advisories` row, published in the heartbeat JSON, shown on `status.html`, and
disclosed in the report's *Measurement conditions* block with the sentence a person can
act on: re-run `olive-calibrate`. No detection parameter, calibration offset, or
threshold is changed by any of it.

**Rejected: adaptive detection** — re-deriving `threshold_dbfs` from the moved baseline,
so the detector keeps catching "the same" events.

It is a tempting design and it would produce nicer-looking continuity. It is rejected
because continuity is exactly what it destroys. Detection parameters are frozen per
capture session on purpose ([ADR-0019](./0019-detection-parameter-provenance.md)) so
that a report can describe each event under the parameters that were active when it was
logged. A threshold that moves on its own makes two nights incomparable, and it does so
invisibly: nobody could later say whether Tuesday had fewer events than Monday or a
higher bar. Worse, a tool that quietly compensates for a microphone that has been moved
will keep producing plausible numbers after the microphone has been pointed at a
different room entirely. The whole reason this project exists is that the numbers have
to survive someone disagreeing with them.

There is also a scope reason. Deciding what a changed baseline *means* — a moved
microphone, a new neighbour, a season, a broken capsule — is a judgement about the
world, and this tool does not make those ([the no-verdict rule](../PROJECT-SCOPE.md)).
It reports the change and names the check to run.

## Consequences
- **Easier:** a long deployment surfaces its own biggest silent failure. The operator
  learns that the baseline moved on the day it moved, not when the numbers look odd
  months later.
- **Easier:** the advisory is auditable. The row records both windows, both deltas, the
  tolerance and how many minutes went into each side, so a reader can see the strength
  of the observation rather than being handed a warning icon.
- **Harder / accepted:** the watch is only as good as its input. With the ambient ledger
  off — the default, because it is a privacy-budget increase
  ([derived-data budget](../audits/derived-data-budget.md)) — there is nothing to
  compare, and every surface says **drift watch unavailable: ambient ledger not
  enabled** rather than reporting a steady baseline. That distinction is enforced by
  tests, because "could not check" rendering as "checked, all clear" is this
  repository's most-repeated defect.
- **Harder / accepted:** the 5 dB default is an order-of-magnitude judgement, not a
  measurement. It is roughly a doubling of perceived loudness and comfortably outside
  the minute-to-minute variation of a settled room, but no long real-world deployment
  has been run to derive a distribution from. It is documented as a default to tune.
- **Accepted:** the watch runs on the existing checkpoint tick
  ([ADR-0021](./0021-time-driven-heartbeat-and-crash-safe-counters.md)), at most once
  per `drift_check_interval_s`. No timer thread, no socket, no new failure path that can
  stop capture: a failure in the watch is logged and capture continues.
