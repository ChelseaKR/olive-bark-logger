# 0006. Raspberry Pi is the primary target; the PWA is the no-hardware alternative

**Status:** Accepted · **Date:** 2026-05-31 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
Evidence of a noise pattern is only worth as much as its coverage. A monitor that runs
when someone remembers to start it produces a record whose gaps are indistinguishable
from quiet. The dispute needs unattended, always-on capture.

A browser tab cannot deliver that: it is throttled when backgrounded, dies with the
tab, and holds its data in the browser profile. But requiring hardware before anyone
can try the tool at all is a steep first step for the exact person this is written for.

## Decision
The **Raspberry Pi service is the primary target** — a Python service reading frames
from `sounddevice`/PortAudio, computing levels in memory, detecting events, and writing
events to SQLite. The **PWA is a supported alternative for people with no hardware**,
using the Web Audio API `AnalyserNode` for levels and IndexedDB for events, with the
same no-audio guarantee.

Primary means the Pi path is where always-on reliability, durability and provenance
work goes first; the PWA gets parity of *semantics*
([ADR-0026](./0026-pwa-as-a-parallel-implementation.md)), not parity of operations.

## Consequences
- **Easier:** unattended reliability work (`resilient_source`, heartbeat, systemd
  hardening — [ADR-0020](./0020-unattended-ops.md)) has one clear home.
- **Harder / accepted:** two implementations of the detector exist and can drift; that
  is what the conformance harness
  ([ADR-0028](./0028-cross-implementation-conformance-harness.md)) is for.
- **Honest limit:** a PWA run is a weaker record than a Pi run and the PWA says so —
  it surfaces its own coverage gaps rather than presenting a partial night as a whole
  one.
