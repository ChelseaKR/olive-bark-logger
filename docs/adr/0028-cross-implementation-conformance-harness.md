# 0028. Golden vectors both implementations replay (FIX-06)

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
[ADR-0026](./0026-pwa-as-a-parallel-implementation.md) accepted two implementations of
the detector on the argument that the core is small. Its residual risk is that they
drift — and detection drift is the worst possible kind, because both sides still pass
their own tests, both still produce a plausible report, and the two reports disagree
about how many times the dog barked. Each suite testing its own port proves internal
consistency and nothing about agreement.

## Decision
A **language-neutral set of golden vectors** in `spec/detector/` (JSON) covering the
boundaries where the two ports could plausibly differ: the `>=` threshold boundary,
minimum-duration filtering, debounce bridging and splitting, flush-at-end, zero minimum
duration, and peak/average taken over loud readings only.

**Both implementations replay the same vectors:** `tests/test_conformance.py` (pytest,
`monitor.detector.Detector`) and `pwa/conformance.test.mjs` (`node --test`,
`pwa/detector.js`), asserting equality to `1e-9`.

`spec/SEMANTICS.md` documents the intentional divergences — no coarse tag, no
calibration, no sessions in the PWA; the CSV timezone difference — and the operating
rule: **changing detection semantics means changing a vector on purpose.** It also notes
the quiet-hours/summarize extension point.

## Consequences
- **Easier:** the two ports cannot drift silently. A semantic change fails in both
  suites until the vector is updated deliberately, which turns an invisible divergence
  into a reviewable decision.
- **The vectors are the specification.** The detector's contract lives in
  `spec/detector/`, not in either implementation, and either one can be read against it.
- **Harder / accepted:** coverage is the boundaries the vectors encode. A behaviour
  neither vector reaches can still diverge, so extending detection means extending the
  vector set, not just the code.
