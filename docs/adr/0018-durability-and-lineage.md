# 0018. Durability and lineage: WAL, a versioned schema, and a sessions table

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
The store holds months of evidence written by an appliance that loses power without
warning. Three separate risks meet in it:

1. **Crash durability.** A default SQLite connection can lose the tail of a run, or
   corrupt the file, on a hard power cut.
2. **Schema evolution.** The record outlives the code that wrote it. Every later
   integrity feature — clock anomalies, parameter provenance, envelope statistics — adds
   columns or tables to a database that already holds real data, and an ad-hoc "add the
   column if it is missing" approach silently produces databases whose shape depends on
   which versions touched them.
3. **Lineage.** An event on its own does not say which device, in which placement,
   under which calibration and zone, produced it — which is exactly what a reader in a
   dispute has to be able to ask.

## Decision
- SQLite runs in **WAL** mode with `synchronous=NORMAL`.
- The schema is **versioned via `user_version`** with in-place migrations
  (`store/db.py`), so a database states its own shape and upgrades are ordered and
  explicit.
- A **`sessions` table** records device, placement, calibration, zone and coverage, and
  **every event links to its session**, so any figure in a report is traceable to the
  run that produced it.
- **Retention pruning is config-driven** rather than manual.

**Rejected: an ad-hoc schema with no upgrade path.**

## Consequences
- **Easier:** every later schema change had somewhere to go. v3 carried clock anomalies
  and parameter provenance, v7 carried envelope statistics, and each migration is a
  reviewable step rather than a shape that emerges from the version history of the
  binary that ran.
- **Easier:** calibration could later become an append-only history applied at render
  time ([ADR-0003](./0003-raw-levels-append-only-calibration.md)) *because* sessions
  already recorded what was in force.
- **Discipline this imposes:** two branches must never both define the same schema
  version — recorded in ADR-0003, and the reason schema numbering is settled in review
  rather than at merge.
- **Harder / accepted:** retention deletes evidence. Pruning had to be made to reach
  every table it should, and to say what it reached, rather than quietly missing tables
  added after it was written.
