# Accessibility Statement — Olive's Bark Logger

**Conformance target:** WCAG 2.2 Level AA.
**Scope:** the generated HTML report (`report.html`, the primary deliverable) and the
browser PWA (`pwa/index.html`).
**Date of this statement:** 2026-08-15 (supersedes 2026-07-05) · **Contact:** open an
issue in this repository, or see `CITATION.cff` for the maintainer.

This statement is the canonical, standalone accessibility declaration (A11Y-16); the
full automated-check table and manual walkthrough evidence it summarizes live in
[`docs/audits/accessibility-2026-06-05.md`](../audits/accessibility-2026-06-05.md).

## Conformance status
**Partially conforms.** The report surface has a merge-blocking structural gate
(`tests/test_a11y.py`) plus an automated axe pass (`pa11y`) in CI, and a manual
walkthrough (keyboard, VoiceOver, 200% zoom, 320px reflow, color independence,
contrast) was performed and passed on 2026-06-05. The PWA surface has automated
Node-level tests for its logic **and, since 2026-07-11, an automated axe pass over
`pwa/index.html` on every push and pull request** — but it has still never been walked
through manually. Automated coverage and a manual pass are different claims, and only the
first is true of the PWA.

## Known gaps (honest, not silently omitted)
1. **The manual walkthrough is stale.** It was performed against the report template
   as of 2026-06-05. Commit `8a9f1eb` (2026-06-29) added the calendar heatmap and
   quiet-hours violation export — a substantial template change — after that date, and
   the walkthrough has not been regenerated against it. Treat the "Partially conforms"
   status above as provisional until it is (tracked:
   `docs/GAP-LEDGER.md#gap-a11y-1--accessibility-lighthouse-ci-regenerate-the-stale-walkthrough-acrvpat-at-pass`).
2. **The PWA (`pwa/index.html`) has had no manual keyboard/screen-reader/zoom/reflow
   pass.** Its detector/report *logic* is unit-tested (Node's test runner,
   `pwa/*.test.mjs`) and `pwa/index.html` itself is scanned by
   `pa11y --runner axe` on every push and pull request (`.github/workflows/ci.yml`, in
   the required `verify` job, since 2026-07-11). An automated scan finds a fraction of
   real barriers; the human pass is the part still missing. No Lighthouse run either.
3. **No Lighthouse CI accessibility score** is collected for either surface.
4. **No target-size (WCAG 2.5.8) check** exists for the PWA's real buttons/inputs.
5. **Screen-reader coverage is VoiceOver/macOS only** — no NVDA+Firefox/Chrome pairing,
   no iOS VoiceOver pass despite the PWA being a mobile-capable surface.
6. **No formal ACR/VPAT** (Accessibility Conformance Report, WCAG edition) has been
   produced.

None of the above are silently dropped: each is listed in
`docs/GAP-LEDGER.md` and sequenced in the remediation plan (P1-7, P2-2).

## What's solid today
- `<html lang="en">`, one `<h1>`, logical heading structure, a working skip link to
  `#main`.
- Every chart has a `<table>` data equivalent with a `<caption>`; every `<svg>` has
  `role="img"` and an `aria-label`.
- `prefers-reduced-motion` is honored; focus is always visible (`:focus-visible`).
- Nothing depends on color alone — bars carry numeric labels and a full data table.
- Automated: `tests/test_a11y.py` (merge-blocking, every CI run) + `pa11y --runner axe`
  against a freshly rendered report **and against `pwa/index.html`** (both
  merge-blocking, every CI run).

## Feedback
If you encounter an accessibility barrier, please open an issue in this repository
describing the barrier, the surface (report vs. PWA), and your assistive technology.
