# 0020. Unattended operation: reconnecting capture, a file heartbeat, a hardened unit

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §8 (GAP-DOC-1)

## Context
The monitor's value is coverage over weeks
([ADR-0006](./0006-raspberry-pi-primary-pwa-alternative.md)), and nobody is watching it.
Three failure modes each turn a running appliance into a silently useless one: a USB
microphone that disconnects and never comes back; a process that dies or wedges with no
one to notice; and a service that has more access to the host and the network than a
level meter has any need for.

## Decision
- **`resilient_source`** (`monitor/capture.py`) reconnects on device failure with capped
  exponential backoff, rather than exiting on the first `PortAudioError`.
- A **heartbeat JSON file** (`monitor/health.py`) is written **atomically** (temp file
  plus `os.replace`) for an external watchdog to read, so a wedged process is
  detectable from outside it.
- A **hardened `systemd` unit** (`deploy/olive-monitor.service`) enforces the
  local-only posture at the OS level too, with `PrivateNetwork` and `ProtectSystem`.

`PrivateNetwork` is the load-bearing one: the no-egress guarantee is tested in-process
([ADR-0022](./0022-runtime-egress-proof.md)), and the unit makes it true of the process
even if a future dependency disagrees.

## Consequences
- **Easier:** a flaky microphone costs minutes of coverage rather than the rest of the
  run, and the loss is counted
  ([ADR-0016](./0016-frame-coverage-accounting.md)) rather than invisible.
- **Deliberate:** the heartbeat is a **file**, not a socket. That is what keeps the
  no-egress gate applicable to the whole runtime, and it is why the socket-based
  watchdog protocol was rejected in
  [ADR-0021](./0021-time-driven-heartbeat-and-crash-safe-counters.md).
- **Harder / accepted:** an external watchdog has to exist for the heartbeat to do
  anything, and this repo does not ship one — it ships the artifact a watchdog reads.
- **Follow-on:** writing the heartbeat only on events made a quiet night look like a
  dead process, which [ADR-0021](./0021-time-driven-heartbeat-and-crash-safe-counters.md)
  fixed.
