# Accessibility Audit — 2026-06-05

**Standard:** WCAG 2.2 AA · **Scope:** the generated HTML report (the primary deliverable).
**Recheck cadence: per report-template change.**

> **Stale as of 2026-07-05.** Commit `8a9f1eb` (2026-06-29) changed the report template
> substantially (calendar heatmap, quiet-hours violation export) after this walkthrough
> was performed, and it has not been regenerated per this file's own cadence. Treat the
> manual-walkthrough rows below as evidence of the *pre-2026-06-29* template, not the
> current one. Tracked: `docs/GAP-LEDGER.md#gap-a11y-1--accessibility-scan-the-pwa-lighthouse-ci-regenerate-the-stale-walkthrough-acrvpat`.
> The canonical, current accessibility statement is [`docs/a11y/STATEMENT.md`](../a11y/STATEMENT.md).

## Automated (auto-gated)

The structural subset is enforced in CI by `tests/test_a11y.py` (merge-blocking):

| Check | Status |
|-------|--------|
| `<html lang="en">` present | ✅ |
| Viewport meta present | ✅ |
| Exactly one `<h1>`, logical `<h2>` structure | ✅ |
| Skip link to `#main` and a `<main id="main">` | ✅ |
| Every chart `<figure>` has a `<table>` data equivalent with `<caption>` | ✅ |
| Every `<svg>` has `role="img"` and an `aria-label` | ✅ |
| Tables use `scope="col"` / `scope="row"` headers | ✅ |
| `prefers-reduced-motion` honored | ✅ |
| Visible focus (`:focus-visible`) | ✅ |

`make a11y` additionally runs **pa11y (axe-core)** against the rendered report when Node
is available. The structural pytest gate is the always-enforced floor; the axe pass is
the deeper automated layer.

## Manual walkthrough (review-gated)

Primary task: *read the noise report and extract the numbers.* The report is static HTML
with no interactive widgets, which keeps the manual surface small.

| Pass | Result | Notes |
|------|--------|-------|
| Keyboard-only | ✅ | Skip link works; tab order is DOM order; no traps (no interactive controls). |
| Screen reader (VoiceOver) | ✅ | Headings navigable; each chart's data is announced via its table; SVG announces its aria-label summary. |
| 200% zoom | ✅ | Single-column layout reflows; no clipping. |
| 320 px reflow | ✅ | `max-width` + intrinsic layout; no horizontal scroll. |
| Color independence | ✅ | Bars carry numeric labels and a full data table; meaning never depends on color. |
| Contrast | ✅ | Body `#111` on `#fff`; bar/axis colors used only decoratively. |

## Accessibility statement

Moved to [`docs/a11y/STATEMENT.md`](../a11y/STATEMENT.md) (A11Y-16: the statement needs
its own dedicated location with a conformance level, known gaps, contact, and date — not
embedded as the last paragraph of a dated audit artifact). That file also carries the
honest "known gaps" list this audit's staleness implies.
