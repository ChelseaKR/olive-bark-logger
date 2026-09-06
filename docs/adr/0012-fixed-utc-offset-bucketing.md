# 0012. Fixed UTC-offset bucketing (`tz_offset_hours`)

**Status:** Superseded by [ADR-0015](./0015-dst-safe-iana-time-zones.md) · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
Daily and hourly distributions and quiet-hours compliance all depend on which local day
and hour a timestamp falls in. Bucketing against the machine's local time makes a
report depend on the machine that rendered it: the same log, rendered on a laptop in
another zone, produces different daily counts and a different quiet-hours verdict.

## Decision
Bucket against a **fixed UTC offset**, configured as `tz_offset_hours`. A single-site
monitor lives in one offset, so a constant is enough, and it makes reports reproducible
across machines.

**Rejected: machine-local time** — non-reproducible reports.

## Consequences
- **Easier:** report output stopped depending on the renderer's host.
- **The defect that superseded this:** a fixed offset is wrong for roughly half the
  year anywhere that observes daylight saving. Quiet hours would shift by an hour
  against the actual local clock the dispute is argued in, and a day boundary would
  land in the wrong place — silently, with the report still reproducible and still
  wrong. [ADR-0015](./0015-dst-safe-iana-time-zones.md) replaced the fixed offset with
  an IANA zone; the reproducibility property that motivated this ADR is preserved
  there, because the zone is configured rather than taken from the host.

`tz_offset_hours` no longer exists in the codebase; the field is `tz`
(`monitor/config.py`). This record is kept because append-only means the wrong turn
stays visible, not because the decision is live.
