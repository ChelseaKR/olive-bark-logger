# 0000. Record architecture decisions here

**Status:** Accepted · **Date:** 2026-07-05

## Context
`docs/ROADMAP.md` already contains well-formed decision records embedded inline (the
"Key decisions (ADRs)" and "Productionization ADRs" sections, ~13 of them) — the
*content* has always been good, but CQ-44/CQ-45/CQ-46 want expensive-to-reverse
decisions recorded as standalone, numbered, append-only files under `docs/adr/`, not
mixed into a living roadmap document that gets edited freely.

## Decision
Use a lightweight MADR-style format for every ADR in this directory:

```markdown
# NNNN. Title

**Status:** Proposed | Accepted | Superseded by NNNN · **Date:** YYYY-MM-DD

## Context
What forces are at play; what problem this decision responds to.

## Decision
The decision itself, stated plainly.

## Consequences
What becomes easier or harder as a result; what was rejected and why.
```

Numbering is sequential and never reused. ADRs are **append-only**: once accepted, a
later change supersedes an ADR by adding a new one and marking the old one
`Status: Superseded by NNNN` — never silently editing the original's Decision section.

The 13 decisions already embedded in `docs/ROADMAP.md` are not being mechanically
migrated in this pass (that's a bulk-conversion task, tracked in
`docs/GAP-LEDGER.md#gap-cq-1--code-quality-python-floor-formal-adr-uvlockfile-pre-commit-hook-wiring-src-layout-hatchling`);
`docs/ROADMAP.md` remains the source of historical record for those until migrated.
New expensive-to-reverse decisions from this point forward get a numbered file here
first.

## Consequences
- Easier: reviewing why a divergence from `/STANDARDS` exists (e.g. the Python-floor
  decision, ADR-0002) without re-deriving it from commit archaeology.
- Harder: nothing, in practice — this is additive process, not a rewrite of existing
  docs.
