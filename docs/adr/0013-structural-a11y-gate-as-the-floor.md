# 0013. The structural a11y gate is the enforced floor; deeper passes layer above it

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
Accessibility here is a release gate, not a nicety: the report is evidence, and the PWA
is the whole product for anyone without hardware. But the three available layers of
accessibility checking have very different costs and very different reach:

- **Structural rules** (one `<h1>`, correct heading nesting, `scope` on table headers,
  an `aria-label` on every chart, a data-table equivalent, no colour-only encoding) are
  mechanically checkable from the markup with no browser.
- **axe/pa11y** catches more, needs Node and a browser, and is therefore an
  environment-dependent gate.
- **A screen-reader walkthrough** catches what neither can — whether the reading order
  and the alt text are actually *useful* — and cannot be automated at all.

Putting the whole gate at the deepest available layer makes it skippable when the
environment is thin, which is precisely when it gets skipped.

## Decision
The **structural subset is the enforced floor**: `tests/test_a11y.py` runs in the
ordinary pytest suite, everywhere, with no browser, and is merge-blocking. `pa11y`/axe
runs as a **deeper layer** in `make a11y` and in CI. The **screen-reader walkthrough
stays review-gated** and human, committed under `docs/audits/`.

## Consequences
- **Easier:** the floor cannot be skipped for want of Node, and it applies to every
  surface the report renderer produces, including the ones added later.
- **Harder / accepted:** the floor is a subset of WCAG and says so. Passing it is not a
  conformance claim, and the tests' docstrings state that.
- **Known open:** the committed walkthrough goes stale after template changes — a real
  incident, recorded in `docs/audits/accessibility-2026-06-05.md` and tracked as
  GAP-A11Y-1. A human gate that nothing reminds you to re-run is the weak point of this
  arrangement, and naming it is part of the decision.
