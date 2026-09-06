# 0015. Bucket and evaluate quiet hours in an IANA zone, not a fixed offset

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)
**Supersedes:** [ADR-0012](./0012-fixed-utc-offset-bucketing.md)

## Context
[ADR-0012](./0012-fixed-utc-offset-bucketing.md) bucketed timestamps against a fixed
UTC offset so that a report did not depend on the machine rendering it. It bought
reproducibility and paid for it with correctness: a fixed offset is wrong for roughly
half the year anywhere that observes daylight saving. Quiet hours would be evaluated an
hour away from the clock the dispute is actually argued in, and day boundaries would
land in the wrong place — with nothing in the output to indicate it.

## Decision
Bucketing and quiet-hours evaluation use an **IANA time zone** resolved through the
standard library's `zoneinfo` (`monitor/config.py`'s `tz`, e.g.
`"America/Los_Angeles"`), not an offset. Quiet-hours windows are reconstructed
concretely day by day in that zone, so a window that crosses a DST transition is the
length the clock says it is.

If `tzdata` is unavailable on the host, `Config.tzinfo()` **falls back to UTC** rather
than raising — the monitor keeps running, which matters more on an appliance than a
correct-or-nothing posture.

**Rejected: a fixed UTC offset** — wrong half the year.

## Consequences
- **Easier:** quiet-hours compliance means what a reader assumes it means.
- **Kept:** the property ADR-0012 was protecting. The zone is *configured*, not read
  from the host, so the same log still renders identically on any machine.
- **Harder / accepted risk:** the UTC fallback is silent at the config layer. On a host
  with no tzdata the report is built in UTC while the config names a zone, and only the
  rendered zone tells the reader. `tzdata` is carried in the dev environment so this
  does not bite in CI, but it is the sharp edge of this decision on a stripped
  deployment image.
- **Stdlib:** `zoneinfo` is stdlib from 3.9, so this costs the zero-dependency core
  ([ADR-0009](./0009-zero-dependency-pure-python-core.md)) nothing.
