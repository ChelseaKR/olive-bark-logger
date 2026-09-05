# 0021. Flush the heartbeat and frame counters on a wall-clock cadence (FIX-04)

**Status:** Accepted · **Date:** 2026-07-02 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
The heartbeat and the session frame counters
([ADR-0020](./0020-unattended-ops.md), [ADR-0016](./0016-frame-coverage-accounting.md))
were written on **events** and in the `finally` block. Both premises fail exactly when
the record matters:

- A genuinely quiet night produces no events, so `updated_at` goes stale and a watchdog
  reads a healthy monitor as dead — the coverage the tool exists to prove is the
  condition that makes it look broken.
- A power cut never reaches the `finally` block, so `frames_seen` / `frames_dropped`
  for the whole run are lost, and the run's coverage becomes unknowable.

The obvious fix is a `systemd` watchdog over `sd_notify`. That imports a socket module
into the monitor, which trips the no-egress guardrail
([ADR-0022](./0022-runtime-egress-proof.md)) — a real cost, not a theoretical one.

## Decision
The heartbeat and the session frame counters are flushed on a **wall-clock cadence**
(`checkpoint_interval_s`, default 30 s), not only on events and at exit. A
**`checkpointed(...)` generator** (`monitor/service.py`, exercised by
`tests/test_checkpoint.py`) piggybacks the periodic write on frame arrival (~10 Hz), so
there is **no timer thread and no socket**.

**Rejected: an `sd_notify`/socket watchdog** — it would import a network module and
trip the no-egress guardrail.

## Consequences
- **Easier:** a silent night keeps `updated_at` fresh, and a power cut leaves the
  last-checkpointed counters on disk instead of losing the run.
- **Deliberate:** the heartbeat stays **file-based**, so the egress gate still covers
  the entire monitor.
- **Harder / accepted:** the cadence is driven by frame arrival, so if capture itself
  stalls, the checkpoint stalls with it. That is the correct behaviour for a liveness
  signal — a heartbeat that keeps ticking while capture is dead would be worse than
  none — but it means the heartbeat measures the capture loop, not the process.
- **Accepted:** up to `checkpoint_interval_s` of counter progress is lost in a crash.
  Bounded and disclosed beats unbounded and silent.
