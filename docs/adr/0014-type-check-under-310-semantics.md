# 0014. Type-check under 3.10 semantics on a 3.9 runtime floor

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
The runtime floor is Python 3.9 ([ADR-0002](./0002-python-39-floor.md)) because that is
what the deployment target ships. Current mypy has dropped support for checking against
3.9, so the type checker and the runtime cannot both be pinned to the same version. The
two options are to freeze mypy at an old release — losing every subsequent fix,
including the ones that catch real bugs — or to check under newer semantics than the
runtime provides.

## Decision
Code **runs on 3.9** and is **checked under 3.10 semantics**. Every module carries
`from __future__ import annotations`, so annotations are strings at runtime and are
never evaluated; the 3.10-only spellings the checker accepts (`X | None` and friends in
annotation position) therefore cost nothing at runtime on 3.9.

## Consequences
- **Easier:** mypy stays current, and annotations read the modern way.
- **Harder / accepted risk — the real one:** the guarantee holds *only* for annotations.
  A 3.10-only construct in an expression that actually executes — a `match` statement,
  a runtime `isinstance(x, int | str)`, a newer stdlib API — type-checks clean and
  fails on the deployment target at run time. The type checker is not the thing
  defending the floor here.
- **Enforced elsewhere:** the 3.9 floor is held by the test matrix actually running on
  3.9, not by mypy. That is why the 2026-08-26 finding — five required
  `test-matrix (macos-latest, …)` checks satisfied by an `echo` — mattered as much as
  it did: while those checks could not fail, this ADR's residual risk had no backstop.
- **Revisit trigger:** when the runtime floor rises, drop the divergence rather than
  carrying it out of habit.
