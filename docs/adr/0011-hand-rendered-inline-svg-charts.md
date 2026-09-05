# 0011. Charts are hand-rendered inline SVG with a paired data table

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
The report needs daily and hourly distributions. Three constraints collide with the
usual plotting library:

1. **Determinism.** The same event log must render the same report, byte for byte, so
   a snapshot test can hold the output. Plotting libraries embed font metrics, versions
   and rasterised output that move under them.
2. **Accessibility.** A chart is evidence here, and a chart a screen reader cannot read
   is evidence withheld from part of the audience
   ([ADR-0013](./0013-structural-a11y-gate-as-the-floor.md)).
3. **The zero-dependency core** ([ADR-0009](./0009-zero-dependency-pure-python-core.md)),
   which rendering is on the wrong side of if a plotting stack is required.

## Decision
Charts are **inline SVG emitted directly by `report/render.py`**, deterministic by
construction, and every chart is paired with a **data table carrying the same numbers**.
The SVG carries `role="img"` and an `aria-label`; the table is the accessible
equivalent, not a fallback.

**Rejected: matplotlib** — heavy, non-deterministic output, and harder to make
accessible than the markup it would replace.

## Consequences
- **Easier:** `tests/test_report_snapshot.py` can byte-compare a golden report, which
  is what makes report regressions visible at all.
- **Easier:** the same semantic HTML feeds the tagged PDF export's structure tree
  ([ADR-0004](./0004-weasyprint-for-tagged-pdf-a-export.md)), so there is no second,
  parallel tagging program to keep in sync.
- **Harder / accepted:** chart types are limited to what is worth hand-writing, and
  each new one carries its own layout code and its own data table.
