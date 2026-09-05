# 0023. Local automation hooks over AF_UNIX, not a localhost port (EXP-11)

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
The single biggest weakness of a level-only record is confounders: the report cannot
say whether a loud stretch was the dog, a vacuum, or the television. A same-host home
automation system (Home Assistant and similar) already knows some of that, and could
correlate it — if the monitor emitted anything at all.

Everything about emitting collides with the no-egress guarantee
([ADR-0022](./0022-runtime-egress-proof.md)). The conventional integration — an HTTP
endpoint or an MQTT publish on `127.0.0.1` — is network egress by any honest reading,
and "it is only localhost" is the argument that erodes a guarantee like this one.

## Decision
An **opt-in, emit-only, one-way feed** of the heartbeat and the per-event dict to a
local **`AF_UNIX` datagram socket** (`--ipc-socket` / `ipc_socket`; `""` disables it,
which is the default). A Unix domain socket is a filesystem object with filesystem
permissions and no network stack behind it.

- Sends are **nonblocking and best-effort**, so a stalled listener cannot freeze
  capture.
- **All `socket` use is confined to `monitor/ipc.py`**, behind a surgical carve-out in
  the no-egress gate.
- **Canary tests prove** the module opens only `AF_UNIX` — never `AF_INET` or
  `AF_INET6` — and that the default path opens no socket at all.
- The README documents a Home Assistant `command_line` example.

**Rejected: an INET/localhost port** — that is network egress.

## Consequences
- **Easier:** confounder context can reach a report from a system that already has it,
  without the monitor ever gaining a network capability.
- **The carve-out is bounded three ways:** one module, one address family (asserted at
  runtime), and off by default. This is the reason the runtime egress proof was worth
  building — a static import scan could not have licensed this exception.
- **Harder / accepted:** the no-egress gate now has an exception, and every future
  reader of it has to understand why. An unexplained carve-out is how a guarantee is
  lost; the canaries are what keep this one explained.
- **One-way, deliberately:** nothing is read back from the socket, so a compromised
  listener cannot influence what the monitor records.
