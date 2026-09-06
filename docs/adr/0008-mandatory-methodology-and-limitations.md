# 0008. Every report carries a methodology-and-limitations section, non-optionally

**Status:** Accepted · **Date:** 2026-05-31 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
This report is handed to a property manager during a dispute. A page of counts and
decibel figures with no statement of how they were produced reads as authoritative
regardless of how weak the underlying measurement is, and the reader has no way to
discount it correctly. The device is a relative meter with an approximate calibration
offset; it cannot attribute a sound to a source; it may have missed hours.

A limitations section that an operator can switch off is not a limitations section. The
moment it is optional, the adversarial version of this report is the one that gets
printed.

## Decision
The methodology and limitations section is **part of the report, not a feature of it**.
Every rendered artifact — HTML report, PDF export, violations report, CSV exports —
carries the statement of how levels were derived, what calibration was in force, what
coverage the run achieved, and what the record cannot show. There is no configuration
flag that removes it.

**Rejected: bare numbers with no limitations**, and rejected equally: making the
section a togglable option.

## Consequences
- **Easier:** the report is credible because it is discountable — a reader can see
  exactly how far to trust it.
- **Enforced:** `tests/test_report_content.py` is merge-blocking, and the caveats were
  made to travel with every export path rather than only the Python one.
- **Downstream:** this decision is why disclosure work keeps landing here — coverage
  ([ADR-0016](./0016-frame-coverage-accounting.md)), clock anomalies
  ([ADR-0017](./0017-clock-integrity-guard.md)), parameter epochs
  ([ADR-0019](./0019-detection-parameter-provenance.md)) — instead of being left as
  operator knowledge.
