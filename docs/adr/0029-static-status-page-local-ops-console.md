# 0029. The local ops console is a static file, not a server (EXP-05)

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
An unattended monitor needs a way to answer "is it working right now?" without SSH and
without waiting for the next report. The natural implementation is a small local
dashboard — which normally means an HTTP server in the monitor process, bound to a
port.

That is a listening socket inside the process whose defining guarantee is that it does
no networking ([ADR-0022](./0022-runtime-egress-proof.md)), and the same "it is only
local" reasoning that was rejected for the automation feed
([ADR-0023](./0023-local-automation-hooks-over-af-unix.md)). It also adds a second way
for the console to take the monitor down: a serving thread that can wedge, leak, or
throw where capture can see it.

## Decision
The monitor renders a **static `status.html`** (`report/status.py`) on each periodic
check-in: latest level, heartbeat freshness, frame coverage, recorded monitoring gaps,
and a recent summary. It is:

- **written atomically** (temp file plus `os.replace`), so a reader never sees a
  half-written page — the same technique as the heartbeat
  ([ADR-0020](./0020-unattended-ops.md));
- **enabled from `health_path`**, or from an explicit `status_path`;
- **best-effort**, so a rendering failure can never stop capture;
- built on the report's **structural a11y floor**
  ([ADR-0013](./0013-structural-a11y-gate-as-the-floor.md)), so the operator console is
  not the surface where accessibility is dropped.

It requires **no server, no network and no audio**.

**Rejected: a live HTTP server** — a static file keeps the local-only, zero-egress
guarantee.

## Consequences
- **Easier:** the console is a file. Open it, `scp` it, serve it from something else if
  you want to — none of which the monitor has to know about.
- **Harder / accepted:** it is as fresh as the last check-in, not live. For a liveness
  view whose whole subject is heartbeat freshness, a timestamped snapshot is honest,
  because the staleness is the reading.
- **Care required:** a status page is a surface that can state an absence as a value.
  Its coverage and gap figures were fixed twice for exactly that — a page claiming 100%
  frame coverage before a frame was ever read, and "no monitoring gaps" implying full
  coverage when the monitor never restarted.
