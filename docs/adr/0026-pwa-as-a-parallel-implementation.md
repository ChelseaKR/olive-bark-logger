# 0026. The PWA is a parallel implementation sharing semantics, not code

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
The browser variant ([ADR-0006](./0006-raspberry-pi-primary-pwa-alternative.md)) needs
the same detector, the same level math and the same report as the Python service, in a
runtime that cannot execute any of them. The options were to compile or transpile the
Python, to run it in the browser through a Python-in-WebAssembly runtime, or to
re-implement the small pure core in JavaScript.

The core in question is genuinely small — RMS to dBFS, a threshold/duration/debounce
state machine, and an aggregation pass — and the alternatives each buy shared code at
the price of a heavy runtime, an offline-hostile download, or a build step, against a
zero-dependency posture ([ADR-0009](./0009-zero-dependency-pure-python-core.md)) and an
install-and-open promise.

## Decision
The PWA **re-implements** the detector, level math and report in JavaScript
(`pwa/detector.js`, `pwa/level.js`, `pwa/report.js`), with its **own Node tests**, and
is documented as a **parallel implementation** that shares the *semantics* and the
honest framing rather than the code.

## Consequences
- **Easier:** the PWA is static files that work offline with no build step, and the
  Python core stays free of any compile-to-JS constraint.
- **Harder / accepted — the whole risk of this decision:** two implementations can
  drift, and a drift in detection semantics is silent and produces two defensible
  reports that disagree. That risk is what
  [ADR-0028](./0028-cross-implementation-conformance-harness.md) exists to hold, and
  this ADR should be read as incomplete without it.
- **Deliberate divergences** — no coarse tag, no calibration history, no sessions in the
  PWA, and a CSV timezone difference — are enumerated in `spec/SEMANTICS.md` rather
  than left to be discovered.
