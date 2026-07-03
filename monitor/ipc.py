"""Opt-in, emit-only local IPC feed for home-automation confounder context.

This is the *one* place in the codebase that touches `socket`, and it is deliberately
narrow: a **one-way, local-only, emit-only** datagram feed over an AF_UNIX socket. It
never binds, never listens, never reads, and never opens an INET socket — there is no
inbound path and nothing leaves the machine. Its sole purpose is to let a local
home-automation listener (e.g. Home Assistant on the same host) correlate confounders
(a doorbell, a vacuum, a smart speaker) with logged noise events.

Design constraints (enforced by the no-egress gate's AF_UNIX carve-out and canary tests):
  * MUST only ever construct ``socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)``.
  * MUST never reference AF_INET/AF_INET6 — a local filesystem socket cannot reach a
    network, which keeps the project's no-network-egress guarantee intact.
  * Best-effort and nonblocking: a missing, dead, or backpressured listener can never
    stall or crash capture; unsent datagrams are dropped.

`socket` is imported here and *only* here so the guardrail stays a single-file exemption.
"""

from __future__ import annotations

import contextlib
import json
import socket


class LocalIpcEmitter:
    """Best-effort, emit-only sender over a local AF_UNIX datagram socket.

    The socket is created lazily on first ``emit`` so constructing an emitter for a
    configured-but-not-yet-listening path is free and side-effect-free.
    """

    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self._sock: socket.socket | None = None

    def _socket(self) -> socket.socket:
        if self._sock is None:
            # The only socket() call in the whole codebase: local datagram, never INET.
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self._sock.setblocking(False)
        return self._sock

    def emit(self, payload: dict[str, object]) -> None:
        """JSON-encode ``payload`` and send it to the configured local socket path.

        One-way and best-effort: if no listener is bound at the path we silently drop
        the datagram rather than let a home-automation integration take down the monitor.
        """
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        # Missing peers, permissions, oversized datagrams, and a full listener queue are
        # all harmless for this best-effort feed. In particular, nonblocking send prevents
        # a bound-but-hung consumer from freezing the capture loop.
        with contextlib.suppress(OSError):
            self._socket().sendto(data, self.socket_path)

    def close(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None
