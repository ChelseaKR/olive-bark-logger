# Accessibility Audit — 2026-06-05

**Standard:** WCAG 2.2 AA · **Scope:** the generated HTML report (the primary deliverable).
**Recheck cadence: per report-template change.**

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

This report aims to meet WCAG 2.2 AA. All chart data is available as text in an adjacent
table, nothing relies on color alone, and the document is fully navigable by keyboard and
screen reader. Report accessibility issues via the project repository.
