# 0022. Prove no egress at runtime, not only by scanning imports

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
"This tool never sends anything anywhere" is one of the three claims the project is
built on. It was checked by a **static import scan**: no module in the runtime imports
`socket`, `http`, `urllib`, and so on.

A static scan checks the shape of the source, not the behaviour of the program. It is
defeated by a deferred import inside a function, by a dependency that opens a
connection on the far side of an import the scan considers innocent, and by any dynamic
import at all. For a claim this load-bearing, source-shape evidence is the weaker half.

## Decision
Keep the static scan **and add a runtime proof**: a test **booby-traps `socket`** and
then runs the **full pipeline and report** (`tests/test_no_egress.py`). Any attempt to
open a connection during real execution fails the test rather than passing a source
inspection.

## Consequences
- **Easier:** the guarantee is checked as behaviour, over the code path a user actually
  runs, and it stays true as dependencies change underneath it.
- **This is what made a carve-out safe.** The one deliberate exception — the local
  `AF_UNIX` automation feed
  ([ADR-0023](./0023-local-automation-hooks-over-af-unix.md)) — could be granted
  precisely because canary tests can prove at runtime that the module opens only
  `AF_UNIX` and never `AF_INET`/`AF_INET6`, and that the default path opens no socket
  at all. A static scan could not have drawn that line.
- **Harder / accepted:** the proof covers the paths the test exercises. It is
  strengthened by running the whole pipeline plus report rather than a unit, and a new
  runtime path that no test drives is outside it.
