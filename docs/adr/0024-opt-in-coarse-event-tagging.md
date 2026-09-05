# 0024. Coarse event tagging is opt-in, feature-based, and hedged in the report

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
"Was it the dog?" is the question the report cannot answer
([ADR-0005](./0005-level-only-no-audio-persisted.md)), and the one a reader most wants
answered. A cheap signal is available without keeping any audio: bark-like sounds have
a different zero-crossing rate profile from ambient noise, and ZCR is computable from a
frame in memory and discarded with it.

The risk is not technical. It is that a coarse heuristic printed next to hard numbers
gets read as a classification, and the report quietly becomes the source-attribution
claim the project promised never to make.

## Decision
Coarse tagging is **opt-in**, computed from an in-memory zero-crossing-rate feature
(`monitor/features.py`) that is discarded with the frame, and stored as a single
`coarse_tag` on the event — bark-like or ambient. In the report it is surfaced as a
**clearly hedged "hint"**, never as a finding, and never as a basis for any count the
report presents as evidence.

**No audio is stored.** The feature is derived and dropped exactly like the level.

## Consequences
- **Easier:** a reader gets a signal about what a loud stretch probably was, without
  the record acquiring a claim it cannot support.
- **Harder / accepted:** the hedging has to survive every export path and every future
  template change. A tag that loses its hedge on the way to a CSV or a PDF is the
  failure mode, and it is the same class as the caveats that had to be made to travel
  with every export path rather than only the HTML one.
- **Off by default, deliberately:** the honest report is the one without the tag, and
  the tag is an addition a user opts into.
